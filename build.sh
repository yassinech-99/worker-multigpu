#!/usr/bin/env bash
set -euo pipefail

set DOCKER_BUILDKIT=1
set HUGGINGFACE_TOKEN="$HUGGINGFACE_TOKEN"
set CIVITAI_API_KEY="$CIVITAI_API_KEY"

# Replace <your-image-name>:<tag> with your desired name and tag
docker build --platform linux/amd64 --progress=plain ^
  --secret id=hf_token,env=HUGGINGFACE_TOKEN ^
  --secret id=civitai_token,env=CIVITAI_API_KEY ^
  -t runpod-comfyui-cine:1.0-base .

# Example for Docker Hub:
docker tag runpod-comfyui-cine:1.0-base shanezhou24/runpod-comfyui-cine:1.0-base

docker login
docker push shanezhou24/runpod-comfyui-cine:1.0-base