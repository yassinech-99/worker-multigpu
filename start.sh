#!/usr/bin/env bash

# Use libtcmalloc for better memory management
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"

# Ensure ComfyUI-Manager runs in offline network mode inside the container
comfy-manager-set-mode offline || echo "worker-comfyui - Could not set ComfyUI-Manager network_mode" >&2

# ----------------------------------------------------------------------------
# MODEL LINKING STEP (Run before ComfyUI starts)
# ----------------------------------------------------------------------------
echo "worker-comfyui: Pre-start model linking..."

# Define the base paths
WORKSPACE_MODELS="/runpod-volume/models"
COMFY_MODELS="/comfyui/models"

# Check if the network volume exists
if [ -d "$WORKSPACE_MODELS" ]; then
    echo "worker-comfyui: Network volume found at $WORKSPACE_MODELS"

    # List of subdirectories to link
    # This covers the Wan2.1 requirements (vae, text_encoders, diffusion_models) and standard folders
    SUBDIRS=(
        "checkpoints" "loras" "vae" "embeddings" "controlnet"
        "upscale_models" "clip" "clip_vision" "style_models"
        "unet" "photo_maker" "ipadapter" "instant_id"
        "animatediff_models" "insightface" "ultralytics" "mmdets"
        "diffusion_models" "text_encoders" "detection" "sam2" "sams" "LLM"
    )

    for subdir in "${SUBDIRS[@]}"; do
        SRC_DIR="$WORKSPACE_MODELS/$subdir"
        DEST_DIR="$COMFY_MODELS/$subdir"

        if [ -d "$SRC_DIR" ]; then
            # Ensure destination directory exists
            mkdir -p "$DEST_DIR"

            # Symlink FILES only.
            # This allows models baked into the image to coexist with volume models.
            # We use 'find' to avoid errors if the directory is empty.
            echo "worker-comfyui: Linking files in $subdir..."
            find "$SRC_DIR" -maxdepth 1 -type f -exec ln -sf {} "$DEST_DIR/" \;
        fi
    done

    echo "worker-comfyui: Model linking complete."
else
    echo "worker-comfyui: No network volume found at $WORKSPACE_MODELS. Skipping linking."
fi
# ----------------------------------------------------------------------------

echo "worker-comfyui: Starting ComfyUI"

# Allow operators to tweak verbosity; default is DEBUG.
: "${COMFY_LOG_LEVEL:=DEBUG}"

# Serve the API and don't shutdown the container
if [ "$SERVE_API_LOCALLY" == "true" ]; then
    python -u /comfyui/main.py --disable-auto-launch --disable-metadata --listen --verbose "${COMFY_LOG_LEVEL}" --log-stdout &

    echo "worker-comfyui: Starting RunPod Handler"
    python -u /handler.py --rp_serve_api --rp_api_host=0.0.0.0
else
    # Standard startup
    python -u /comfyui/main.py --disable-auto-launch --disable-metadata --listen --verbose "${COMFY_LOG_LEVEL}" --log-stdout &

    echo "worker-comfyui: Starting RunPod Handler"
    python -u /handler.py
fi