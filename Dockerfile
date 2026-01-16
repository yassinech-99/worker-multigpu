## Start from a clean base image
FROM ghcr.io/yassinech-99/runpod-comfyui-worker:latest AS base

## Add metadata labels
LABEL maintainer="your-@example.com" \
      description="Production-optimized ComfyUI with custom nodes and models" \
      version="2.0"

## Set environment variables early for better caching
ENV TORCH_CUDA_ARCH_LIST="8.9;9.0" \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

## Install system dependencies and Python packages
## Split into separate layers for better debugging and caching
RUN pip install -U wheel setuptools packaging

## Install PyTorch with CUDA 12.8 support
## Using explicit versions from PyTorch official repository
RUN pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 \
    --index-url https://download.pytorch.org/whl/cu128

## Install xformers and triton separately to avoid conflicts
RUN pip install xformers triton

## Install build dependencies for flash_attn compilation
RUN pip install ninja packaging

## Install flash_attn with limited parallel jobs to avoid memory issues
## This will take 3-5 minutes to compile
ENV MAX_JOBS=4
RUN pip install flash_attn==2.7.4.post1 --no-build-isolation || \
    echo "Warning: flash_attn installation failed, continuing without it"

## Install ComfyUI custom nodes (group related operations)
RUN comfy-node-install ComfyUI-Apt_Preset && \
    comfy-node-install ComfyUI-WanAnimatePreprocess && \
    comfy-node-install comfyui-segment-anything-2 && \
    comfy-node-install wanblockswap

## Manually install ComfyUI-SeCNode (consolidated into single RUN)
RUN cd /comfyui/custom_nodes && \
    git clone https://github.com/9nate-drake/Comfyui-SecNodes && \
    cd Comfyui-SecNodes && \
    pip install -r requirements.txt

## Install SageAttention using pip (pre-built wheel, faster and no compilation needed)
## This avoids needing CUDA toolkit in the build environment
RUN pip install sageattention || echo "Warning: SageAttention installation failed, continuing without it"

## Set final working directory
WORKDIR /

## Copy application files (these change most frequently, so place at end)
COPY handler.py ./
COPY input/ /comfyui/input/

COPY start.sh /start.sh
RUN chmod +x /start.sh
## Optional: Uncomment if you need these
# COPY . .
# RUN chmod +x /entrypoint.sh
# CMD ["/entrypoint.sh"]