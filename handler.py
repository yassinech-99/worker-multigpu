import runpod
from runpod.serverless.utils import rp_upload
import json
import urllib.request
import urllib.parse
import time
import os
import requests
import base64
from io import BytesIO
import websocket
import uuid
import tempfile
import socket
import traceback

# Time to wait between API check attempts in milliseconds
COMFY_API_AVAILABLE_INTERVAL_MS = 50
# Maximum number of API check attempts
COMFY_API_AVAILABLE_MAX_RETRIES = 500
# Websocket reconnection behaviour (can be overridden through environment variables)
WEBSOCKET_RECONNECT_ATTEMPTS = int(os.environ.get("WEBSOCKET_RECONNECT_ATTEMPTS", 5))
WEBSOCKET_RECONNECT_DELAY_S = int(os.environ.get("WEBSOCKET_RECONNECT_DELAY_S", 3))

# Extra verbose websocket trace logs
if os.environ.get("WEBSOCKET_TRACE", "false").lower() == "true":
    websocket.enableTrace(True)

# Host where ComfyUI is running
COMFY_HOST = "127.0.0.1:8188"
# Enforce a clean state after each job is done
REFRESH_WORKER = os.environ.get("REFRESH_WORKER", "false").lower() == "true"

# ComfyUI directories - CRITICAL FOR VHS NODES
COMFYUI_INPUT_DIR = "/comfyui/input/"
COMFYUI_OUTPUT_DIR = "/comfyui/output/"

def _comfy_server_status():
    """Return a dictionary with basic reachability info for the ComfyUI HTTP server."""
    try:
        resp = requests.get(f"http://{COMFY_HOST}/", timeout=5)
        return {
            "reachable": resp.status_code == 200,
            "status_code": resp.status_code,
        }
    except Exception as exc:
        return {"reachable": False, "error": str(exc)}

def _attempt_websocket_reconnect(ws_url, max_attempts, delay_s, initial_error):
    """
    Attempts to reconnect to the WebSocket server after a disconnect.
    """
    print(f"worker-comfyui - Websocket connection closed unexpectedly: {initial_error}. Attempting to reconnect...")
    last_reconnect_error = initial_error
    for attempt in range(max_attempts):
        srv_status = _comfy_server_status()
        if not srv_status["reachable"]:
            print(f"worker-comfyui - ComfyUI HTTP unreachable – aborting websocket reconnect: {srv_status.get('error', 'status '+str(srv_status.get('status_code')))}")
            raise websocket.WebSocketConnectionClosedException(
                "ComfyUI HTTP unreachable during websocket reconnect"
            )

        print(f"worker-comfyui - Reconnect attempt {attempt + 1}/{max_attempts}... (ComfyUI HTTP reachable, status {srv_status.get('status_code')})")
        try:
            new_ws = websocket.WebSocket()
            new_ws.connect(ws_url, timeout=10)
            print(f"worker-comfyui - Websocket reconnected successfully.")
            return new_ws
        except (
            websocket.WebSocketException,
            ConnectionRefusedError,
            socket.timeout,
            OSError,
        ) as reconn_err:
            last_reconnect_error = reconn_err
            print(f"worker-comfyui - Reconnect attempt {attempt + 1} failed: {reconn_err}")
            if attempt < max_attempts - 1:
                print(f"worker-comfyui - Waiting {delay_s} seconds before next attempt...")
                time.sleep(delay_s)
            else:
                print(f"worker-comfyui - Max reconnection attempts reached.")

    print("worker-comfyui - Failed to reconnect websocket after connection closed.")
    raise websocket.WebSocketConnectionClosedException(
        f"Connection closed and failed to reconnect. Last error: {last_reconnect_error}"
    )

def validate_input(job_input):
    """
    Validates the input for the handler function.
    """
    if job_input is None:
        return None, "Please provide input"

    if isinstance(job_input, str):
        try:
            job_input = json.loads(job_input)
        except json.JSONDecodeError:
            return None, "Invalid JSON format in input"

    workflow = job_input.get("workflow")
    if workflow is None:
        return None, "Missing 'workflow' parameter"

    # Validate images
    images = job_input.get("images")
    if images is not None:
        if not isinstance(images, list):
            return None, "'images' must be a list"

        for image in images:
            if not isinstance(image, dict):
                return None, "Each image must be an object"

            name = image.get("name")
            url = image.get("url")
            path = image.get("path")

            if not name:
                return None, "Each image must have a 'name'"

            if url is None and path is None:
                return None, "Each image must have either 'url' or 'path'"

            if url and path:
                return None, "Image cannot have both 'url' and 'path'"

    # Validate audio files
    audio_files = job_input.get("audio")
    if audio_files is not None:
        if not isinstance(audio_files, list):
            return None, "'audio' must be a list"

        for audio in audio_files:
            if not isinstance(audio, dict):
                return None, "Each audio file must be an object"

            name = audio.get("name")
            url = audio.get("url")
            path = audio.get("path")

            if not name:
                return None, "Each audio file must have a 'name'"

            if url is None and path is None:
                return None, "Each audio file must have either 'url' or 'path'"

            if url and path:
                return None, "Audio file cannot have both 'url' and 'path'"

    # Validate video files
    video_files = job_input.get("video")
    if video_files is not None:
        if not isinstance(video_files, list):
            return None, "'video' must be a list"

        for video in video_files:
            if not isinstance(video, dict):
                return None, "Each video file must be an object"

            name = video.get("name")
            url = video.get("url")
            path = video.get("path")

            if not name:
                return None, "Each video file must have a 'name'"

            if url is None and path is None:
                return None, "Each video file must have either 'url' or 'path'"

            if url and path:
                return None, "Video file cannot have both 'url' and 'path'"

    comfy_org_api_key = job_input.get("comfy_org_api_key")

    return {
        "workflow": workflow,
        "images": images,
        "audio": audio_files,
        "video": video_files,
        "comfy_org_api_key": comfy_org_api_key,
    }, None

def check_server(url, retries=500, delay=50):
    """
    Check if a server is reachable via HTTP GET request
    """
    print(f"worker-comfyui - Checking API server at {url}...")
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"worker-comfyui - API is reachable")
                return True
        except requests.Timeout:
            pass
        except requests.RequestException as e:
            pass

        time.sleep(delay / 1000)

    print(f"worker-comfyui - Failed to connect to server at {url} after {retries} attempts.")
    return False

def download_file_from_url(url, timeout=120):
    """
    Download file from URL.
    """
    try:
        print(f"worker-comfyui - Downloading file from URL: {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        print(f"worker-comfyui - Error downloading file from URL {url}: {e}")
        return None

def load_file_from_path(file_path):
    """
    Load file from local file path.
    """
    try:
        print(f"worker-comfyui - Loading file from path: {file_path}")
        with open(file_path, 'rb') as f:
            return f.read()
    except Exception as e:
        print(f"worker-comfyui - Error loading file from path {file_path}: {e}")
        return None

def upload_media_files(media_files, media_type):
    """
    Upload media files (images, audio, video) to ComfyUI from URLs or local file paths.
    """
    if not media_files:
        return {"status": "success", "message": f"No {media_type} files to upload", "details": []}

    # For video files, use direct filesystem method
    if media_type == 'video':
        return upload_video_files_direct(media_files)

    responses = []
    upload_errors = []

    print(f"worker-comfyui - Processing {len(media_files)} {media_type} file(s)...")

    endpoint_map = {
        'image': '/upload/image',
        'audio': '/upload/audio',
    }

    field_map = {
        'image': 'image',
        'audio': 'audio',
    }

    endpoint = endpoint_map.get(media_type, '/upload/image')
    field_name = field_map.get(media_type, 'file')

    for media_file in media_files:
        try:
            name = media_file["name"]
            url = media_file.get("url")
            path = media_file.get("path")

            # Get file data from URL or local path
            if url:
                file_data = download_file_from_url(url)
            elif path:
                file_data = load_file_from_path(path)
            else:
                error_msg = f"{media_type.capitalize()} {name} has neither URL nor path"
                print(f"worker-comfyui - {error_msg}")
                upload_errors.append(error_msg)
                continue

            if file_data is None:
                error_msg = f"Failed to get file data for {name}"
                print(f"worker-comfyui - {error_msg}")
                upload_errors.append(error_msg)
                continue

            # Determine MIME type
            file_ext = os.path.splitext(name)[1].lower()
            mime_type = "application/octet-stream"

            if media_type == 'image':
                if file_ext in ['.jpg', '.jpeg']:
                    mime_type = 'image/jpeg'
                elif file_ext == '.png':
                    mime_type = 'image/png'
                elif file_ext == '.gif':
                    mime_type = 'image/gif'
                elif file_ext == '.webp':
                    mime_type = 'image/webp'
                else:
                    mime_type = 'image/png'
            elif media_type == 'audio':
                if file_ext in ['.mp3', '.mpeg']:
                    mime_type = 'audio/mpeg'
                elif file_ext == '.wav':
                    mime_type = 'audio/wav'
                elif file_ext == '.ogg':
                    mime_type = 'audio/ogg'
                elif file_ext == '.flac':
                    mime_type = 'audio/flac'
                else:
                    mime_type = 'audio/mpeg'

            # Prepare the form data
            files = {
                field_name: (name, BytesIO(file_data), mime_type),
                "overwrite": (None, "true"),
            }

            # POST request to upload the file
            response = requests.post(
                f"http://{COMFY_HOST}{endpoint}", files=files, timeout=60
            )
            response.raise_for_status()

            responses.append(f"Successfully uploaded {name}")
            print(f"worker-comfyui - Successfully uploaded {name}")

        except requests.Timeout:
            error_msg = f"Timeout uploading {media_file.get('name', 'unknown')}"
            print(f"worker-comfyui - {error_msg}")
            upload_errors.append(error_msg)
        except requests.RequestException as e:
            error_msg = f"Error uploading {media_file.get('name', 'unknown')}: {e}"
            print(f"worker-comfyui - {error_msg}")
            upload_errors.append(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error uploading {media_file.get('name', 'unknown')}: {e}"
            print(f"worker-comfyui - {error_msg}")
            upload_errors.append(error_msg)

    if upload_errors:
        print(f"worker-comfyui - {media_type} file(s) upload finished with errors")
        return {
            "status": "error",
            "message": f"Some {media_type} files failed to upload",
            "details": upload_errors,
        }

    print(f"worker-comfyui - {media_type} file(s) upload complete")
    return {
        "status": "success",
        "message": f"All {media_type} files uploaded successfully",
        "details": responses,
    }

def upload_video_files_direct(video_files):
    """
    Upload video files directly to ComfyUI input directory.
    """
    if not video_files:
        return {"status": "success", "message": "No video files to upload", "details": []}

    responses = []
    upload_errors = []

    print(f"worker-comfyui - Processing {len(video_files)} video file(s) via direct filesystem...")

    for video in video_files:
        try:
            name = video["name"]
            url = video.get("url")
            path = video.get("path")

            # Get video data from URL or local path
            if url:
                print(f"worker-comfyui - Downloading video from URL: {url}")
                video_data = download_file_from_url(url, timeout=120)
            elif path:
                print(f"worker-comfyui - Loading video from path: {path}")
                video_data = load_file_from_path(path)
            else:
                error_msg = f"Video {name} has neither URL nor path"
                print(f"worker-comfyui - {error_msg}")
                upload_errors.append(error_msg)
                continue

            if video_data is None:
                error_msg = f"Failed to get video data for {name}"
                print(f"worker-comfyui - {error_msg}")
                upload_errors.append(error_msg)
                continue

            # Write video directly to ComfyUI input directory
            output_path = os.path.join(COMFYUI_INPUT_DIR, name)
            with open(output_path, 'wb') as f:
                f.write(video_data)

            responses.append(f"Successfully wrote video to {output_path}")
            print(f"worker-comfyui - Successfully wrote video to {output_path}")

        except Exception as e:
            error_msg = f"Error writing video {video.get('name', 'unknown')}: {e}"
            print(f"worker-comfyui - {error_msg}")
            upload_errors.append(error_msg)

    if upload_errors:
        print(f"worker-comfyui - Video file(s) upload finished with errors")
        return {
            "status": "error",
            "message": "Some video files failed to upload",
            "details": upload_errors,
        }

    print(f"worker-comfyui - Video file(s) upload complete")
    return {
        "status": "success",
        "message": "All video files uploaded successfully",
        "details": responses,
    }

def get_available_models():
    """
    Get list of available models from ComfyUI
    """
    try:
        response = requests.get(f"http://{COMFY_HOST}/object_info", timeout=10)
        response.raise_for_status()
        object_info = response.json()

        available_models = {}
        if "CheckpointLoaderSimple" in object_info:
            checkpoint_info = object_info["CheckpointLoaderSimple"]
            if "input" in checkpoint_info and "required" in checkpoint_info["input"]:
                ckpt_options = checkpoint_info["input"]["required"].get("ckpt_name")
                if ckpt_options and len(ckpt_options) > 0:
                    available_models["checkpoints"] = (
                        ckpt_options[0] if isinstance(ckpt_options[0], list) else []
                    )

        return available_models
    except Exception as e:
        print(f"worker-comfyui - Warning: Could not fetch available models: {e}")
        return {}

def queue_workflow(workflow, client_id, comfy_org_api_key=None):
    """
    Queue a workflow to be processed by ComfyUI
    """
    payload = {"prompt": workflow, "client_id": client_id}

    key_from_env = os.environ.get("COMFY_ORG_API_KEY")
    effective_key = comfy_org_api_key if comfy_org_api_key else key_from_env
    if effective_key:
        payload["extra_data"] = {"api_key_comfy_org": effective_key}
    data = json.dumps(payload).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    response = requests.post(
        f"http://{COMFY_HOST}/prompt", data=data, headers=headers, timeout=30
    )

    if response.status_code == 400:
        print(f"worker-comfyui - ComfyUI returned 400. Response body: {response.text}")
        try:
            error_data = response.json()
            print(f"worker-comfyui - Parsed error data: {error_data}")

            error_message = "Workflow validation failed"
            error_details = []

            if "error" in error_data:
                error_info = error_data["error"]
                if isinstance(error_info, dict):
                    error_message = error_info.get("message", error_message)
                    if error_info.get("type") == "prompt_outputs_failed_validation":
                        error_message = "Workflow validation failed"
                else:
                    error_message = str(error_info)

            if "node_errors" in error_data:
                for node_id, node_error in error_data["node_errors"].items():
                    if isinstance(node_error, dict):
                        for error_type, error_msg in node_error.items():
                            error_details.append(
                                f"Node {node_id} ({error_type}): {error_msg}"
                            )
                    else:
                        error_details.append(f"Node {node_id}: {node_error}")

            if error_data.get("type") == "prompt_outputs_failed_validation":
                error_message = error_data.get("message", "Workflow validation failed")
                available_models = get_available_models()
                if available_models.get("checkpoints"):
                    error_message += f"\n\nThis usually means a required model or parameter is not available."
                    error_message += f"\nAvailable checkpoint models: {', '.join(available_models['checkpoints'])}"
                else:
                    error_message += "\n\nThis usually means a required model or parameter is not available."
                    error_message += "\nNo checkpoint models appear to be available. Please check your model installation."

                raise ValueError(error_message)

            if error_details:
                detailed_message = f"{error_message}:\n" + "\n".join(
                    f"• {detail}" for detail in error_details
                )

                if any(
                    "not in list" in detail and "ckpt_name" in detail
                    for detail in error_details
                ):
                    available_models = get_available_models()
                    if available_models.get("checkpoints"):
                        detailed_message += f"\n\nAvailable checkpoint models: {', '.join(available_models['checkpoints'])}"
                    else:
                        detailed_message += "\n\nNo checkpoint models appear to be available. Please check your model installation."

                raise ValueError(detailed_message)
            else:
                raise ValueError(f"{error_message}. Raw response: {response.text}")

        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(
                f"ComfyUI validation failed (could not parse error response): {response.text}"
            )

    response.raise_for_status()
    return response.json()

def get_history(prompt_id):
    """
    Retrieve the history of a given prompt using its ID
    """
    response = requests.get(f"http://{COMFY_HOST}/history/{prompt_id}", timeout=30)
    response.raise_for_status()
    return response.json()

def get_file_data(filename, subfolder, file_type):
    """
    Fetch file bytes - check both /view endpoint AND local output directory.
    """
    print(f"worker-comfyui - Fetching file data: type={file_type}, subfolder={subfolder}, filename={filename}")

    # Try API endpoint first (for temp files)
    try:
        data = {"filename": filename, "subfolder": subfolder, "type": file_type}
        url_values = urllib.parse.urlencode(data)
        response = requests.get(f"http://{COMFY_HOST}/view?{url_values}", timeout=60)
        response.raise_for_status()
        print(f"worker-comfyui - Successfully fetched file data for {filename} via /view")
        return response.content
    except requests.RequestException as e:
        print(f"worker-comfyui - Could not fetch {filename} via /view: {e}. Trying local directory...")

    # If API fails, check local output directory (for VHS saved files)
    try:
        # Build local path
        local_path = os.path.join(COMFYUI_OUTPUT_DIR, filename)

        if subfolder:
            local_path = os.path.join(COMFYUI_OUTPUT_DIR, subfolder, filename)

        if os.path.exists(local_path):
            print(f"worker-comfyui - Found {filename} locally at {local_path}")
            with open(local_path, 'rb') as f:
                return f.read()
        else:
            # Try to find any file with similar name (VHS adds timestamps)
            if os.path.exists(COMFYUI_OUTPUT_DIR):
                output_files = os.listdir(COMFYUI_OUTPUT_DIR)
                matching_files = [f for f in output_files if filename in f]

                if matching_files:
                    # Get most recent file
                    latest_file = max(matching_files, key=lambda f: os.path.getmtime(os.path.join(COMFYUI_OUTPUT_DIR, f)))
                    latest_path = os.path.join(COMFYUI_OUTPUT_DIR, latest_file)
                    print(f"worker-comfyui - Found similar file: {latest_file}")
                    with open(latest_path, 'rb') as f:
                        return f.read()
                else:
                    print(f"worker-comfyui - File not found in output directory: {filename}")
            else:
                print(f"worker-comfyui - Output directory does not exist: {COMFYUI_OUTPUT_DIR}")

            return None

    except Exception as e:
        print(f"worker-comfyui - Error reading local file {filename}: {e}")
        return None

def get_content_type(file_type, file_extension):
    """
    Get the appropriate content type for S3 upload based on file type and extension.
    """
    file_extension = file_extension.lower() if file_extension else ''

    if file_type == "image":
        if file_extension in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif file_extension == '.png':
            return 'image/png'
        elif file_extension == '.gif':
            return 'image/gif'
        elif file_extension == '.webp':
            return 'image/webp'
        else:
            return 'image/png'

    elif file_type == "audio":
        if file_extension in ['.mp3', '.mpeg']:
            return 'audio/mpeg'
        elif file_extension == '.wav':
            return 'audio/wav'
        elif file_extension == '.ogg':
            return 'audio/ogg'
        elif file_extension == '.flac':
            return 'audio/flac'
        else:
            return 'audio/mpeg'

    elif file_type == "video":
        if file_extension == '.mp4':
            return 'video/mp4'
        elif file_extension == '.avi':
            return 'video/x-msvideo'
        elif file_extension == '.mov':
            return 'video/quicktime'
        elif file_extension == '.webm':
            return 'video/webm'
        elif file_extension == '.gif':
            return 'image/gif'
        else:
            return 'video/mp4'

    return 'application/octet-stream'

def process_single_file(filename, file_bytes, job_id, file_type, errors):
    """
    Process a single file (image, audio, video) and return output data.
    UPDATED: Uses upload_file_to_bucket with temporary file to support extra_args.
    """
    file_extension = os.path.splitext(filename)[1] or f".{file_type}"

    # First check if S3 is configured and try to upload
    if os.environ.get("BUCKET_ENDPOINT_URL"):
        try:
            print(f"worker-comfyui - Attempting S3 upload for {filename} ({len(file_bytes)} bytes)")

            # Create a temporary file to use upload_file_to_bucket
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                tmp_file.write(file_bytes)
                tmp_file_path = tmp_file.name

            content_type = get_content_type(file_type, file_extension)

            # Use upload_file_to_bucket which supports extra_args
            s3_url = rp_upload.upload_file_to_bucket(
                file_name=filename,
                file_location=tmp_file_path,
                bucket_name=None,
                prefix=job_id,
                extra_args={'ContentType': content_type}
            )

            # Clean up temporary file
            os.unlink(tmp_file_path)

            print(f"worker-comfyui - Uploaded {filename} to S3: {s3_url}")
            return {
                "filename": filename,
                "type": file_type,
                "storage": "s3_url",
                "data": s3_url,
            }

        except Exception as e:
            error_msg = f"Error uploading {filename} to S3: {e}"
            print(f"worker-comfyui - {error_msg}")
            errors.append(error_msg)
            # Fall back to base64 on S3 error
            print(f"worker-comfyui - Falling back to base64 for {filename}")
            return process_as_base64(filename, file_bytes, file_type, errors)
    else:
        # No S3 configured, use base64
        print(f"worker-comfyui - No S3 configured, using base64 for {filename}")
        return process_as_base64(filename, file_bytes, file_type, errors)

def process_as_base64(filename, file_bytes, file_type, errors):
    """
    Process file as base64 data when S3 is not available or fails.
    FIXED: Better handling for large files.
    """
    try:
        # For all file types, check size first
        max_base64_size = 5 * 1024 * 1024  # 5MB limit for RunPod API

        if len(file_bytes) < max_base64_size:
            base64_data = base64.b64encode(file_bytes).decode("utf-8")
            print(f"worker-comfyui - Encoded {filename} as base64 ({len(file_bytes)} bytes -> {len(base64_data)} chars)")
            return {
                "filename": filename,
                "type": file_type,
                "storage": "base64",
                "data": base64_data,
                "size_bytes": len(file_bytes)
            }
        else:
            # File too large for base64, return metadata only
            print(f"worker-comfyui - File {filename} too large for base64 ({len(file_bytes)} bytes)")
            return {
                "filename": filename,
                "type": file_type,
                "storage": "local",
                "size_bytes": len(file_bytes),
                "message": f"File too large for base64 encoding ({len(file_bytes)} bytes). File saved locally at /comfyui/output/{filename}"
            }
    except Exception as e:
        error_msg = f"Error processing {filename} as base64: {e}"
        print(f"worker-comfyui - {error_msg}")
        errors.append(error_msg)
        return None

def process_outputs(outputs, job_id):
    """
    Process outputs from ComfyUI workflow execution.
    FIXED: Now correctly handles VHS output format.
    """
    output_data = []
    errors = []

    print(f"worker-comfyui - Processing {len(outputs)} output nodes...")

    # DEBUG: List all nodes and their outputs
    for node_id, node_output in outputs.items():
        print(f"worker-comfyui - DEBUG Node {node_id} output keys: {list(node_output.keys())}")

        # 1. HANDLE VHS_VideoCombine OUTPUT (CRITICAL FIX)
        # VHS outputs can be under 'gifs' or 'video' key. It returns a list of dictionaries.
        vhs_output = None
        output_key = None

        if "gifs" in node_output:
            vhs_output = node_output["gifs"]
            output_key = "gifs"
        elif "video" in node_output:
            vhs_output = node_output["video"]
            output_key = "video"
        elif "animated" in node_output:
            vhs_output = node_output["animated"]
            output_key = "animated"

        if vhs_output is not None:
            print(f"worker-comfyui - Found VHS output in key '{output_key}': {vhs_output}")

            # VHS OUTPUT FORMAT FIX: It's a LIST containing DICTIONARIES, not [bool, [filepaths]]
            if isinstance(vhs_output, list) and len(vhs_output) > 0:
                # Handle each dictionary in the list
                for item in vhs_output:
                    if isinstance(item, dict):
                        filename = item.get("filename")
                        subfolder = item.get("subfolder", "")
                        fullpath = item.get("fullpath")

                        if fullpath:
                            # Use fullpath if available
                            filepath = fullpath
                        elif filename:
                            # Build path from filename and subfolder
                            if subfolder:
                                filepath = os.path.join(COMFYUI_OUTPUT_DIR, subfolder, filename)
                            else:
                                filepath = os.path.join(COMFYUI_OUTPUT_DIR, filename)
                        else:
                            print(f"worker-comfyui - No filename or fullpath in VHS item: {item}")
                            continue

                        print(f"worker-comfyui - Processing VHS file: {filepath}")

                        # Extract just the filename from the full path
                        filename_only = os.path.basename(filepath)

                        # Try to read the file
                        if os.path.exists(filepath):
                            print(f"worker-comfyui - Reading VHS output from: {filepath}")
                            try:
                                with open(filepath, 'rb') as f:
                                    file_bytes = f.read()

                                # Process as video file
                                result = process_single_file(filename_only, file_bytes, job_id, "video", errors)
                                if result:
                                    output_data.append(result)
                                    print(f"worker-comfyui - Successfully processed VHS video: {filename_only}")
                                else:
                                    print(f"worker-comfyui - process_single_file returned None for: {filename_only}")
                                    errors.append(f"Failed to process VHS video: {filename_only}")
                            except Exception as e:
                                error_msg = f"Error reading VHS file {filepath}: {e}"
                                print(f"worker-comfyui - {error_msg}")
                                errors.append(error_msg)
                        else:
                            # File not found at expected path
                            print(f"worker-comfyui - VHS file not found at {filepath}")

                            # Try alternative: search for filename in output directory
                            if os.path.exists(COMFYUI_OUTPUT_DIR):
                                all_files = os.listdir(COMFYUI_OUTPUT_DIR)
                                matching_files = [f for f in all_files if filename_only in f or (filename and filename in f)]

                                if matching_files:
                                    # Get most recent matching file
                                    matching_files.sort(key=lambda f: os.path.getmtime(os.path.join(COMFYUI_OUTPUT_DIR, f)), reverse=True)
                                    latest_file = matching_files[0]
                                    latest_path = os.path.join(COMFYUI_OUTPUT_DIR, latest_file)

                                    print(f"worker-comfyui - Found alternative file: {latest_file}")
                                    try:
                                        with open(latest_path, 'rb') as f:
                                            file_bytes = f.read()

                                        result = process_single_file(latest_file, file_bytes, job_id, "video", errors)
                                        if result:
                                            output_data.append(result)
                                    except Exception as e:
                                        errors.append(f"Error reading alternative file {latest_file}: {e}")
                                else:
                                    errors.append(f"Could not find VHS output file: {filename_only}")
                    elif isinstance(item, str):
                        # Handle string filenames (legacy format)
                        filename = item
                        print(f"worker-comfyui - Processing VHS filename string: {filename}")

                        local_path = os.path.join(COMFYUI_OUTPUT_DIR, filename)
                        if os.path.exists(local_path):
                            with open(local_path, 'rb') as f:
                                file_bytes = f.read()
                            result = process_single_file(filename, file_bytes, job_id, "video", errors)
                            if result:
                                output_data.append(result)
            else:
                print(f"worker-comfyui - VHS output is not a list or is empty: {vhs_output}")

        # 2. Handle images (original code)
        if "images" in node_output:
            print(f"worker-comfyui - Node {node_id} contains {len(node_output['images'])} image(s)")
            for image_info in node_output["images"]:
                filename = image_info.get("filename")
                subfolder = image_info.get("subfolder", "")
                img_type = image_info.get("type")

                if img_type == "temp":
                    print(f"worker-comfyui - Skipping image {filename} because type is 'temp'")
                    continue

                if not filename:
                    warn_msg = f"Skipping image in node {node_id} due to missing filename: {image_info}"
                    print(f"worker-comfyui - {warn_msg}")
                    errors.append(warn_msg)
                    continue

                file_bytes = get_file_data(filename, subfolder, img_type)

                if file_bytes:
                    result = process_single_file(filename, file_bytes, job_id, "image", errors)
                    if result:
                        output_data.append(result)
                    else:
                        print(f"worker-comfyui - process_single_file returned None for image: {filename}")
                else:
                    error_msg = f"Failed to fetch image data for {filename}"
                    errors.append(error_msg)

        # 3. Handle audio files
        if "audio" in node_output:
            print(f"worker-comfyui - Node {node_id} contains {len(node_output['audio'])} audio file(s)")
            for audio_info in node_output["audio"]:
                filename = audio_info.get("filename")
                subfolder = audio_info.get("subfolder", "")
                audio_type = audio_info.get("type")

                if not filename:
                    warn_msg = f"Skipping audio in node {node_id} due to missing filename: {audio_info}"
                    print(f"worker-comfyui - {warn_msg}")
                    errors.append(warn_msg)
                    continue

                file_bytes = get_file_data(filename, subfolder, audio_type)

                if file_bytes:
                    result = process_single_file(filename, file_bytes, job_id, "audio", errors)
                    if result:
                        output_data.append(result)
                    else:
                        print(f"worker-comfyui - process_single_file returned None for audio: {filename}")
                else:
                    error_msg = f"Failed to fetch audio data for {filename}"
                    errors.append(error_msg)

        # 4. Handle other output types
        other_keys = [k for k in node_output.keys() if k not in ["images", "audio", "video", "gifs", "animated"]]
        if other_keys:
            warn_msg = f"Node {node_id} produced unhandled output keys: {other_keys}."
            print(f"worker-comfyui - WARNING: {warn_msg}")

    return output_data, errors

def handler(job):
    """
    Handles a job using ComfyUI via websockets for status and file retrieval.
    """

    # Model links are now handled by start.sh

    job_input = job["input"]
    job_id = job["id"]

    validated_data, error_message = validate_input(job_input)
    if error_message:
        return {"error": error_message}

    workflow = validated_data["workflow"]
    input_images = validated_data.get("images")
    input_audio = validated_data.get("audio")
    input_video = validated_data.get("video")

    if not check_server(
        f"http://{COMFY_HOST}/",
        COMFY_API_AVAILABLE_MAX_RETRIES,
        COMFY_API_AVAILABLE_INTERVAL_MS,
    ):
        return {
            "error": f"ComfyUI server ({COMFY_HOST}) not reachable after multiple retries."
        }

    # Upload input files
    if input_images:
        upload_result = upload_media_files(input_images, "image")
        if upload_result["status"] == "error":
            return {
                "error": "Failed to upload one or more input images",
                "details": upload_result["details"],
            }

    if input_audio:
        upload_result = upload_media_files(input_audio, "audio")
        if upload_result["status"] == "error":
            return {
                "error": "Failed to upload one or more input audio files",
                "details": upload_result["details"],
            }

    if input_video:
        upload_result = upload_media_files(input_video, "video")
        if upload_result["status"] == "error":
            return {
                "error": "Failed to upload one or more input video files",
                "details": upload_result["details"],
            }

    ws = None
    client_id = str(uuid.uuid4())
    prompt_id = None
    output_data = []
    errors = []

    try:
        ws_url = f"ws://{COMFY_HOST}/ws?clientId={client_id}"
        print(f"worker-comfyui - Connecting to websocket: {ws_url}")
        ws = websocket.WebSocket()
        ws.connect(ws_url, timeout=10)
        print(f"worker-comfyui - Websocket connected")

        try:
            queued_workflow = queue_workflow(
                workflow,
                client_id,
                comfy_org_api_key=validated_data.get("comfy_org_api_key"),
            )
            prompt_id = queued_workflow.get("prompt_id")
            if not prompt_id:
                raise ValueError(f"Missing 'prompt_id' in queue response: {queued_workflow}")
            print(f"worker-comfyui - Queued workflow with ID: {prompt_id}")
        except requests.RequestException as e:
            print(f"worker-comfyui - Error queuing workflow: {e}")
            raise ValueError(f"Error queuing workflow: {e}")
        except Exception as e:
            print(f"worker-comfyui - Unexpected error queuing workflow: {e}")
            if isinstance(e, ValueError):
                raise e
            else:
                raise ValueError(f"Unexpected error queuing workflow: {e}")

        print(f"worker-comfyui - Waiting for workflow execution ({prompt_id})...")
        execution_done = False
        while True:
            try:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message.get("type") == "status":
                        status_data = message.get("data", {}).get("status", {})
                        print(f"worker-comfyui - Status update: {status_data.get('exec_info', {}).get('queue_remaining', 'N/A')} items remaining in queue")
                    elif message.get("type") == "executing":
                        data = message.get("data", {})
                        if data.get("node") is None and data.get("prompt_id") == prompt_id:
                            print(f"worker-comfyui - Execution finished for prompt {prompt_id}")
                            execution_done = True
                            break
                    elif message.get("type") == "execution_error":
                        data = message.get("data", {})
                        if data.get("prompt_id") == prompt_id:
                            error_details = f"Node Type: {data.get('node_type')}, Node ID: {data.get('node_id')}, Message: {data.get('exception_message')}"
                            print(f"worker-comfyui - Execution error received: {error_details}")
                            errors.append(f"Workflow execution error: {error_details}")
                            break
                else:
                    continue
            except websocket.WebSocketTimeoutException:
                print(f"worker-comfyui - Websocket receive timed out. Still waiting...")
                continue
            except websocket.WebSocketConnectionClosedException as closed_err:
                try:
                    ws = _attempt_websocket_reconnect(
                        ws_url,
                        WEBSOCKET_RECONNECT_ATTEMPTS,
                        WEBSOCKET_RECONNECT_DELAY_S,
                        closed_err,
                    )
                    print("worker-comfyui - Resuming message listening after successful reconnect.")
                    continue
                except websocket.WebSocketConnectionClosedException as reconn_failed_err:
                    raise reconn_failed_err
            except json.JSONDecodeError:
                print(f"worker-comfyui - Received invalid JSON message via websocket.")

        if not execution_done and not errors:
            raise ValueError("Workflow monitoring loop exited without confirmation of completion or error.")

        print(f"worker-comfyui - Fetching history for prompt {prompt_id}...")
        history = get_history(prompt_id)

        if prompt_id not in history:
            error_msg = f"Prompt ID {prompt_id} not found in history after execution."
            print(f"worker-comfyui - {error_msg}")
            if not errors:
                return {"error": error_msg}
            else:
                errors.append(error_msg)
                return {
                    "error": "Job processing failed, prompt ID not found in history.",
                    "details": errors,
                }

        prompt_history = history.get(prompt_id, {})
        outputs = prompt_history.get("outputs", {})

        if not outputs:
            warning_msg = f"No outputs found in history for prompt {prompt_id}."
            print(f"worker-comfyui - {warning_msg}")
            if not errors:
                errors.append(warning_msg)

        # Process all outputs (images, audio, video)
        output_data, output_errors = process_outputs(outputs, job_id)
        errors.extend(output_errors)

    except websocket.WebSocketException as e:
        print(f"worker-comfyui - WebSocket Error: {e}")
        print(traceback.format_exc())
        return {"error": f"WebSocket communication error: {e}"}
    except requests.RequestException as e:
        print(f"worker-comfyui - HTTP Request Error: {e}")
        print(traceback.format_exc())
        return {"error": f"HTTP communication error with ComfyUI: {e}"}
    except ValueError as e:
        print(f"worker-comfyui - Value Error: {e}")
        print(traceback.format_exc())
        return {"error": str(e)}
    except Exception as e:
        print(f"worker-comfyui - Unexpected Handler Error: {e}")
        print(traceback.format_exc())
        return {"error": f"An unexpected error occurred: {e}"}
    finally:
        if ws and ws.connected:
            print(f"worker-comfyui - Closing websocket connection.")
            ws.close()

    final_result = {}

    # Only process non-None output data
    valid_output_data = [item for item in output_data if item is not None]

    if valid_output_data:
        # Group outputs by type
        final_result["outputs"] = valid_output_data
        # Also provide separate lists for convenience
        final_result["images"] = [item for item in valid_output_data if item.get("type") == "image"]
        final_result["audio"] = [item for item in valid_output_data if item.get("type") == "audio"]
        final_result["video"] = [item for item in valid_output_data if item.get("type") == "video"]

    if errors:
        final_result["errors"] = errors
        print(f"worker-comfyui - Job completed with errors/warnings: {errors}")

    if not valid_output_data and errors:
        print(f"worker-comfyui - Job failed with no output files.")
        return {
            "error": "Job processing failed",
            "details": errors,
        }
    elif not valid_output_data and not errors:
        print(f"worker-comfyui - Job completed successfully, but the workflow produced no files.")
        final_result["status"] = "success_no_outputs"
        final_result["outputs"] = []

    print(f"worker-comfyui - Job completed. Returning {len(valid_output_data)} output file(s).")
    return final_result

if __name__ == "__main__":
    print("worker-comfyui - Starting handler...")
    runpod.serverless.start({"handler": handler})