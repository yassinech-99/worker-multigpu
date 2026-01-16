#!/usr/bin/env bash
set -euo pipefail

# Qwen Image series model downloader (wget only)
# Downloads public and gated assets into ./models subdirectories.
# Supports authenticated downloads from Hugging Face (HUGGINGFACE_TOKEN) and Civitai (CIVITAI_API_KEY).

if ! command -v wget >/dev/null 2>&1; then
  echo "Error: 'wget' is required but not found in PATH." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

MODELS_DIR="$SCRIPT_DIR/models"

UNET_DIR="$MODELS_DIR/unet"
CLIP_DIR="$MODELS_DIR/clip"
VAE_DIR="$MODELS_DIR/vae"
LORAS_DIR="$MODELS_DIR/loras"
LLM_DIR="$MODELS_DIR/LLM"

mkdir -p \
  "$UNET_DIR" \
  "$CLIP_DIR" \
  "$VAE_DIR" \
  "$LORAS_DIR" \
  "$LLM_DIR"

# Download from Hugging Face (uses HUGGINGFACE_TOKEN if available for gated models)
download_huggingface() {
  local url="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [ -f "$dest" ]; then
    echo "Exists: $dest (skipping)"
    return 0
  fi
  
  if [ -n "${HUGGINGFACE_TOKEN:-}" ]; then
    echo "Downloading (HF with auth): $url -> $dest"
    wget --header="Authorization: Bearer $HUGGINGFACE_TOKEN" -c "$url" -O "$dest"
  else
    echo "Downloading (HF public): $url -> $dest"
    wget -c "$url" -O "$dest"
  fi
}

# Download from Civitai (requires CIVITAI_API_KEY)
download_civitai() {
  local model_version_id="$1" dest="$2"
  local url="https://civitai.com/api/download/models/$model_version_id"
  
  mkdir -p "$(dirname "$dest")"
  if [ -f "$dest" ]; then
    echo "Exists: $dest (skipping)"
    return 0
  fi
  
  if [ -z "${CIVITAI_API_KEY:-}" ]; then
    echo "Error: CIVITAI_API_KEY not set, cannot download from Civitai" >&2
    return 1
  fi
  
  echo "Downloading (Civitai): $url -> $dest"
  wget --header="Authorization: Bearer $CIVITAI_API_KEY" -c "$url" -O "$dest"
}

# Diffusion model
download_huggingface \
  "https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2509_fp8_e4m3fn.safetensors" \
  "$UNET_DIR/qwen_image_edit_2509_fp8_e4m3fn.safetensors"

# Text encoder
download_huggingface \
  "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
  "$CLIP_DIR/qwen_2.5_vl_7b_fp8_scaled.safetensors"

# VAE
download_huggingface \
  "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" \
  "$VAE_DIR/qwen_image_vae.safetensors"

# LoRAs
download_huggingface \
  "https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors" \
  "$LORAS_DIR/Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors"

download_huggingface \
  "https://huggingface.co/ostris/qwen_image_edit_inpainting/resolve/main/qwen_image_edit_inpainting.safetensors" \
  "$LORAS_DIR/qwen_image_edit_inpainting.safetensors"

download_huggingface \
  "https://huggingface.co/dooszypehnees/consistence_edit_v2/resolve/main/consistence_edit_v2.safetensors" \
  "$LORAS_DIR/consistence_edit_v2.safetensors"

download_huggingface \
  "https://huggingface.co/DiffSynth-Studio/Qwen-Image-Edit-F2P/resolve/main/edit_0928_lora_step40000.safetensors" \
  "$LORAS_DIR/qwen_image_edit_F2P_0928_lora_step40000.safetensors"

# Civitai LoRA
download_civitai \
  "2422860" \
  "$LORAS_DIR/RoleScene_Blend.safetensors"

# LLM
download_huggingface \
  "https://huggingface.co/microsoft/Florence-2-base/resolve/main/model.safetensors" \
  "$LLM_DIR/microsoft/Florence-2-base.safetensors"  

echo "Done. Models saved under: $MODELS_DIR"



