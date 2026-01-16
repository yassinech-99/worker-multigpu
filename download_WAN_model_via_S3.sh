#!/usr/bin/env bash
set -euo pipefail

# Stream WAN Video series models directly into a Runpod Network Volume
# using S3-compatible AWS CLI. Objects are uploaded under s3://$S3_BUCKET/models/...

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

# Helper: upload to S3 only if missing
s3_upload_if_missing() {
  local url="$1"   # source HTTP(S) URL
  local key="$2"   # destination key under s3://$S3_BUCKET

  # Exists? skip
  if aws s3 ls "s3://$S3_BUCKET/$key" --endpoint-url "$S3_ENDPOINT" >/dev/null 2>&1; then
    echo "Exists: s3://$S3_BUCKET/$key (skipping)"
    return 0
  fi

  echo "Uploading: $url -> s3://$S3_BUCKET/$key"
  # Stream via stdin to avoid temporary local files
  curl -L --fail "$url" |
    aws s3 cp - "s3://$S3_BUCKET/$key" \
      --endpoint-url "$S3_ENDPOINT" \
      --content-type application/octet-stream \
      --only-show-errors
}

BASE_PREFIX="models"

# WAN2.2 Animate models
s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors" \
  "$BASE_PREFIX/vae/Wan2_1_VAE_bf16.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors" \
  "$BASE_PREFIX/clip_vision/clip_vision_h.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors" \
  "$BASE_PREFIX/text_encoders/umt5-xxl-enc-bf16.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors" \
  "$BASE_PREFIX/diffusion_models/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors"

# Detection models
s3_upload_if_missing \
  "https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx" \
  "$BASE_PREFIX/detection/yolov10m.onnx"

s3_upload_if_missing \
  "https://huggingface.co/Kijai/vitpose_comfy/resolve/main/onnx/vitpose_h_wholebody_model.onnx" \
  "$BASE_PREFIX/detection/vitpose_h_wholebody_model.onnx"

s3_upload_if_missing \
  "https://huggingface.co/Kijai/vitpose_comfy/resolve/main/onnx/vitpose_h_wholebody_data.bin" \
  "$BASE_PREFIX/detection/vitpose_h_wholebody_data.bin"

# LoRA models
s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors" \
  "$BASE_PREFIX/loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors" \
  "$BASE_PREFIX/loras/WanAnimate_relight_lora_fp16.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Pusa/Wan21_PusaV1_LoRA_14B_rank512_bf16.safetensors" \
  "$BASE_PREFIX/loras/Wan21_PusaV1_LoRA_14B_rank512_bf16.safetensors"

# WAN2.2 T2V VACE models
s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Fun/VACE/Wan2_2_Fun_VACE_module_A14B_HIGH_bf16.safetensors" \
  "$BASE_PREFIX/diffusion_models/Wan2_2_Fun_VACE_module_A14B_HIGH_bf16.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Fun/VACE/Wan2_2_Fun_VACE_module_A14B_LOW_bf16.safetensors" \
  "$BASE_PREFIX/diffusion_models/Wan2_2_Fun_VACE_module_A14B_LOW_bf16.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/Scooiii/SmoothMixT2V/resolve/main/smoothMixWan22I2VT2V_t2vHighV20.safetensors" \
  "$BASE_PREFIX/diffusion_models/smoothMixWan22I2VT2V_t2vHighV20.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors" \
  "$BASE_PREFIX/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors" \
  "$BASE_PREFIX/loras/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"

# WAN2.1 T2V VACE models
s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-VACE_module_14B_bf16.safetensors" \
  "$BASE_PREFIX/diffusion_models/Wan2_1-VACE_module_14B_bf16.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-T2V-14B_fp8_e4m3fn.safetensors" \
  "$BASE_PREFIX/diffusion_models/Wan2_1-T2V-14B_fp8_e4m3fn.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors" \
  "$BASE_PREFIX/loras/Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors"

# Segmentation models
s3_upload_if_missing \
  "https://huggingface.co/Kijai/sam2-safetensors/resolve/main/sam2.1_hiera_large-fp16.safetensors" \
  "$BASE_PREFIX/sam2/sam2.1_hiera_large-fp16.safetensors"

s3_upload_if_missing \
  "https://huggingface.co/VeryAladeen/Sec-4B/resolve/main/SeC-4B-fp16.safetensors" \
  "$BASE_PREFIX/sams/SeC-4B-fp16.safetensors"

# LLM
s3_upload_if_missing \
  "https://huggingface.co/microsoft/Florence-2-base/resolve/main/model.safetensors" \
  "$BASE_PREFIX/LLM/microsoft/Florence-2-base.safetensors"

echo "Done. Objects uploaded under s3://$S3_BUCKET/$BASE_PREFIX (endpoint: $S3_ENDPOINT)"

