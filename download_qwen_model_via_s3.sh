#!/usr/bin/env bash
set -euo pipefail

# Stream Qwen Image series models directly into a Runpod Network Volume
# using S3-compatible AWS CLI. Objects are uploaded under s3://$S3_BUCKET/models/...
# Supports authenticated downloads from Hugging Face (HUGGINGFACE_TOKEN) and Civitai (CIVITAI_API_KEY).

# Requirements:
# - aws CLI v2
# - curl
#
# Environment (.env supported in this dir):
# - RUNPOD_API_KEY: used as AWS_ACCESS_KEY_ID
# - S3_API_KEY:     used as AWS_SECRET_ACCESS_KEY
# - S3_ENDPOINT:    S3-compatible endpoint URL (e.g. https://s3.us-west-2.amazonaws.com or your Runpod NV endpoint)
# - S3_BUCKET:      Target bucket name backing your Runpod Network Volume
# - S3_REGION:      Optional; defaults to us-east-1
# - HUGGINGFACE_TOKEN: Optional; used for authenticated Hugging Face gated model downloads
# - CIVITAI_API_KEY: Optional; used for authenticated Civitai downloads

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "Error: 'aws' CLI is required but not found in PATH." >&2
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "Error: 'curl' is required but not found in PATH." >&2
  exit 1
fi

: "${S3_ENDPOINT:?S3_ENDPOINT is required (your Runpod NV S3 endpoint)}"
: "${S3_BUCKET:?S3_BUCKET is required (your Runpod NV bucket name)}"

# Map provided keys to AWS credentials
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-${RUNPOD_API_KEY:-}}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-${S3_API_KEY:-}}"
export AWS_DEFAULT_REGION="${S3_REGION:-us-east-1}"

if [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  echo "Error: AWS credentials not set. Provide RUNPOD_API_KEY and S3_API_KEY in .env or set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY." >&2
  exit 1
fi

# Upload Hugging Face model to S3 (uses HUGGINGFACE_TOKEN if available for gated models)
s3_upload_huggingface() {
  local url="$1"   # source Hugging Face URL
  local key="$2"   # destination key under s3://$S3_BUCKET

  # Exists? skip
  if aws s3 ls "s3://$S3_BUCKET/$key" --endpoint-url "$S3_ENDPOINT" >/dev/null 2>&1; then
    echo "Exists: s3://$S3_BUCKET/$key (skipping)"
    return 0
  fi

  if [ -n "${HUGGINGFACE_TOKEN:-}" ]; then
    echo "Uploading (HF with auth): $url -> s3://$S3_BUCKET/$key"
    curl -L --fail -H "Authorization: Bearer $HUGGINGFACE_TOKEN" "$url" |
      aws s3 cp - "s3://$S3_BUCKET/$key" \
        --endpoint-url "$S3_ENDPOINT" \
        --content-type application/octet-stream \
        --only-show-errors
  else
    echo "Uploading (HF public): $url -> s3://$S3_BUCKET/$key"
    curl -L --fail "$url" |
      aws s3 cp - "s3://$S3_BUCKET/$key" \
        --endpoint-url "$S3_ENDPOINT" \
        --content-type application/octet-stream \
        --only-show-errors
  fi
}

# Upload Civitai model to S3 (requires CIVITAI_API_KEY)
s3_upload_civitai() {
  local model_version_id="$1"   # Civitai model version ID
  local key="$2"                # destination key under s3://$S3_BUCKET
  local url="https://civitai.com/api/download/models/$model_version_id"

  # Exists? skip
  if aws s3 ls "s3://$S3_BUCKET/$key" --endpoint-url "$S3_ENDPOINT" >/dev/null 2>&1; then
    echo "Exists: s3://$S3_BUCKET/$key (skipping)"
    return 0
  fi

  if [ -z "${CIVITAI_API_KEY:-}" ]; then
    echo "Error: CIVITAI_API_KEY not set, cannot download from Civitai" >&2
    return 1
  fi

  echo "Uploading (Civitai): $url -> s3://$S3_BUCKET/$key"
  # Stream via stdin to avoid temporary local files
  curl -L --fail -H "Authorization: Bearer $CIVITAI_API_KEY" "$url" |
    aws s3 cp - "s3://$S3_BUCKET/$key" \
      --endpoint-url "$S3_ENDPOINT" \
      --content-type application/octet-stream \
      --only-show-errors
}

BASE_PREFIX="models"

# Diffusion model
s3_upload_huggingface \
  "https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2509_fp8_e4m3fn.safetensors" \
  "$BASE_PREFIX/unet/qwen_image_edit_2509_fp8_e4m3fn.safetensors"

# Text encoder
s3_upload_huggingface \
  "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
  "$BASE_PREFIX/clip/qwen_2.5_vl_7b_fp8_scaled.safetensors"

# VAE
s3_upload_huggingface \
  "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" \
  "$BASE_PREFIX/vae/qwen_image_vae.safetensors"

# LoRAs
s3_upload_huggingface \
  "https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors" \
  "$BASE_PREFIX/loras/Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors"

s3_upload_huggingface \
  "https://huggingface.co/ostris/qwen_image_edit_inpainting/resolve/main/qwen_image_edit_inpainting.safetensors" \
  "$BASE_PREFIX/loras/qwen_image_edit_inpainting.safetensors"

s3_upload_huggingface \
  "https://huggingface.co/dooszypehnees/consistence_edit_v2/resolve/main/consistence_edit_v2.safetensors" \
  "$BASE_PREFIX/loras/consistence_edit_v2.safetensors"

s3_upload_huggingface \
  "https://huggingface.co/DiffSynth-Studio/Qwen-Image-Edit-F2P/resolve/main/edit_0928_lora_step40000.safetensors" \
  "$BASE_PREFIX/loras/qwen_image_edit_F2P_0928_lora_step40000.safetensors"

# Civitai LoRA
s3_upload_civitai \
  "2422860" \
  "$BASE_PREFIX/loras/RoleScene_Blend.safetensors"

# LLM
s3_upload_huggingface \
  "https://huggingface.co/microsoft/Florence-2-base/resolve/main/model.safetensors" \
  "$BASE_PREFIX/LLM/microsoft/Florence-2-base.safetensors"

echo "Done. Objects uploaded under s3://$S3_BUCKET/$BASE_PREFIX (endpoint: $S3_ENDPOINT)"


