#!/usr/bin/env bash
set -euo pipefail

# WAN Video series model downloader (wget only)
# Downloads public assets into ./models subdirectories.

if ! command -v wget >/dev/null 2>&1; then
  echo "Error: 'wget' is required but not found in PATH." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$SCRIPT_DIR/models"

UNET_DIR="$MODELS_DIR/unet"
CLIP_DIR="$MODELS_DIR/clip"
CLIP_VISION_DIR="$MODELS_DIR/clip_vision"
VAE_DIR="$MODELS_DIR/vae"
LORAS_DIR="$MODELS_DIR/loras"
DIFFUSION_DIR="$MODELS_DIR/diffusion_models"
TEXT_ENCODER_DIR="$MODELS_DIR/text_encoders"
DETECTION_DIR="$MODELS_DIR/detection"
SAM2_DIR="$MODELS_DIR/sam2"
SAMS_DIR="$MODELS_DIR/sams"
LLM_DIR="$MODELS_DIR/LLM"

mkdir -p \
  "$UNET_DIR" \
  "$CLIP_DIR" \
  "$CLIP_VISION_DIR" \
  "$VAE_DIR" \
  "$LORAS_DIR" \
  "$DIFFUSION_DIR" \
  "$TEXT_ENCODER_DIR" \
  "$DETECTION_DIR" \
  "$SAM2_DIR" \
  "$SAMS_DIR" \
  "$LLM_DIR"

download() {
  local url="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [ -f "$dest" ]; then
    echo "Exists: $dest (skipping)"
    return 0
  fi
  echo "Downloading: $url -> $dest"
  wget -c "$url" -O "$dest"
}

# WAN2.2 Animate models
download \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors" \
  "$VAE_DIR/Wan2_1_VAE_bf16.safetensors"

download \
  "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors" \
  "$CLIP_VISION_DIR/clip_vision_h.safetensors"

download \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors" \
  "$TEXT_ENCODER_DIR/umt5-xxl-enc-bf16.safetensors"

download \
  "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors" \
  "$DIFFUSION_DIR/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors"

# Detection models
download \
  "https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx" \
  "$DETECTION_DIR/yolov10m.onnx"

download \
  "https://huggingface.co/Kijai/vitpose_comfy/resolve/main/onnx/vitpose_h_wholebody_model.onnx" \
  "$DETECTION_DIR/vitpose_h_wholebody_model.onnx"

download \
  "https://huggingface.co/Kijai/vitpose_comfy/resolve/main/onnx/vitpose_h_wholebody_data.bin" \
  "$DETECTION_DIR/vitpose_h_wholebody_data.bin"

# LoRA models
download \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors" \
  "$LORAS_DIR/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors"

download \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors" \
  "$LORAS_DIR/WanAnimate_relight_lora_fp16.safetensors"

download \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Pusa/Wan21_PusaV1_LoRA_14B_rank512_bf16.safetensors" \
  "$LORAS_DIR/Wan21_PusaV1_LoRA_14B_rank512_bf16.safetensors"

# WAN2.2 T2V VACE models
download \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Fun/VACE/Wan2_2_Fun_VACE_module_A14B_HIGH_bf16.safetensors" \
  "$DIFFUSION_DIR/Wan2_2_Fun_VACE_module_A14B_HIGH_bf16.safetensors"

download \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Fun/VACE/Wan2_2_Fun_VACE_module_A14B_LOW_bf16.safetensors" \
  "$DIFFUSION_DIR/Wan2_2_Fun_VACE_module_A14B_LOW_bf16.safetensors"

download \
  "https://huggingface.co/Scooiii/SmoothMixT2V/resolve/main/smoothMixWan22I2VT2V_t2vHighV20.safetensors" \
  "$DIFFUSION_DIR/smoothMixWan22I2VT2V_t2vHighV20.safetensors"

download \
  "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors" \
  "$DIFFUSION_DIR/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors"

download \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors" \
  "$LORAS_DIR/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"

# WAN2.1 T2V VACE models
download \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-VACE_module_14B_bf16.safetensors" \
  "$DIFFUSION_DIR/Wan2_1-VACE_module_14B_bf16.safetensors"

download \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-T2V-14B_fp8_e4m3fn.safetensors" \
  "$DIFFUSION_DIR/Wan2_1-T2V-14B_fp8_e4m3fn.safetensors"

download \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors" \
  "$LORAS_DIR/Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors"

# Segmentation models
download \
  "https://huggingface.co/Kijai/sam2-safetensors/resolve/main/sam2.1_hiera_large-fp16.safetensors" \
  "$SAM2_DIR/sam2.1_hiera_large-fp16.safetensors"

download \
  "https://huggingface.co/VeryAladeen/Sec-4B/resolve/main/SeC-4B-fp16.safetensors" \
  "$SAMS_DIR/SeC-4B-fp16.safetensors"

# LLM
download \
  "https://huggingface.co/microsoft/Florence-2-base/resolve/main/model.safetensors" \
  "$LLM_DIR/microsoft/Florence-2-base.safetensors"

echo "Done. Models saved under: $MODELS_DIR"

