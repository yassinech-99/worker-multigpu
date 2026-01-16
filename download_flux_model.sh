#!/usr/bin/env bash
set -euo pipefail

# Downloads required FLUX models using either wget (with HF token) or
# huggingface-cli if wget is unavailable. Requires HUGGINGFACE_TOKEN.

if command -v wget >/dev/null 2>&1; then
  DOWNLOADER="wget"
elif command -v huggingface-cli >/dev/null 2>&1; then
  DOWNLOADER="hf"
else
  echo "Error: require 'wget' or 'huggingface-cli' to download models." >&2
  echo "Install one of them and re-run this script." >&2
  exit 1
fi

: "${HUGGINGFACE_TOKEN:?Environment variable HUGGINGFACE_TOKEN is required}"
export HUGGINGFACE_HUB_TOKEN="$HUGGINGFACE_TOKEN"
: "${CIVITAI_API_KEY:=}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$SCRIPT_DIR/models"

mkdir -p \
  "$MODELS_DIR/unet" \
  "$MODELS_DIR/vae" \
  "$MODELS_DIR/clip" \
  "$MODELS_DIR/style_models"

HF_BASE="https://huggingface.co"

# URLs for direct downloads (used when wget is available)
FILL_URL="$HF_BASE/black-forest-labs/FLUX.1-Fill-dev/resolve/main/flux1-fill-dev.safetensors"
KONTEXT_URL="$HF_BASE/black-forest-labs/FLUX.1-Kontext-dev/resolve/main/flux1-kontext-dev.safetensors"
REDUX_URL="$HF_BASE/black-forest-labs/FLUX.1-Redux-dev/resolve/main/flux1-redux-dev.safetensors"
AE_URL="$HF_BASE/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors"
CLIP_L_URL="$HF_BASE/black-forest-labs/FLUX.1-dev/resolve/main/clip_l.safetensors"
T5_URL="$HF_BASE/black-forest-labs/FLUX.1-dev/resolve/main/t5xxl_fp16.safetensors"

download_with_wget() {
  local url="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [ -f "$dest" ]; then
    echo "Exists: $dest (skipping)"
    return 0
  fi
  echo "Downloading (wget): $url -> $dest"
  wget --header="Authorization: Bearer $HUGGINGFACE_TOKEN" -c "$url" -O "$dest"
}

download_with_hf() {
  local repo="$1" file="$2" local_dir="$3" dest="$local_dir/$2"
  mkdir -p "$local_dir"
  if [ -f "$dest" ]; then
    echo "Exists: $dest (skipping)"
    return 0
  fi
  echo "Downloading (huggingface-cli): $repo:$file -> $local_dir"
  huggingface-cli download "$repo" "$file" \
    --local-dir "$local_dir" \
    --local-dir-use-symlinks False
}

if [ "$DOWNLOADER" = "wget" ]; then
  download_with_wget "$FILL_URL"    "$MODELS_DIR/unet/flux1-fill-dev.safetensors"
  download_with_wget "$KONTEXT_URL" "$MODELS_DIR/unet/flux1-kontext-dev.safetensors"
  download_with_wget "$REDUX_URL"   "$MODELS_DIR/style_models/flux1-redux-dev.safetensors"
  download_with_wget "$AE_URL"      "$MODELS_DIR/vae/ae.safetensors"
  download_with_wget "$CLIP_L_URL"  "$MODELS_DIR/clip/clip_l.safetensors"
  download_with_wget "$T5_URL"      "$MODELS_DIR/clip/t5xxl_fp16.safetensors"
else
  download_with_hf "black-forest-labs/FLUX.1-Fill-dev"    "flux1-fill-dev.safetensors"        "$MODELS_DIR/unet"
  download_with_hf "black-forest-labs/FLUX.1-Kontext-dev" "flux1-kontext-dev.safetensors"      "$MODELS_DIR/unet"
  download_with_hf "black-forest-labs/FLUX.1-Redux-dev"   "flux1-redux-dev.safetensors"        "$MODELS_DIR/style_models"
  download_with_hf "black-forest-labs/FLUX.1-dev"         "ae.safetensors"                     "$MODELS_DIR/vae"
  download_with_hf "black-forest-labs/FLUX.1-dev"         "clip_l.safetensors"                 "$MODELS_DIR/clip"
  download_with_hf "black-forest-labs/FLUX.1-dev"         "t5xxl_fp16.safetensors"             "$MODELS_DIR/clip"
fi

echo "Done. Models saved under: $MODELS_DIR"



