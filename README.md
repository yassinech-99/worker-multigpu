***Runpod ComfyUI Worker Payload***


## URL
```
 {
  "input": {
    "workflow": { /* your full workflow JSON here, with a loader node that fetches URL */ },
    "images": [
      {
        "name": "ref_image.png",
        "url": "https://example.com/path/to/first_frame_edited_1.png"
      }
    ],
    "video": [
      {
        "name": "driving_video.mp4",
        "url": "https://example.com/path/to/driving_video.mp4"
      }
    ]
  }
 ```
 ## PATH
```
{
  "input": {
    "workflow": { /* your full workflow JSON here, with a loader node that fetches path */ },
    "images": [
      {
        "name": "ref_image.png",
        "path": "/comfyui/input/first_frame_edited_1.png"
      }
    ],
    "video": [
      {
        "name": "driving_video.mp4",
        "path": "/comfyui/input/driving_video.mp4"
      }
    ]
  }
}

```

## Execution time

```
{
  "input": {
    "workflow": { /* your full workflow JSON here */ },
    "images": [
      {
        "name": "ref_image.png",
        "path": "/comfyui/input/first_frame_edited_1.png"
      }
    ],
    "video": [
      {
        "name": "driving_video.mp4",
        "path": "/comfyui/input/driving_video_1.mp4"
      }
    ]
  },
  "policy": {
    "executionTimeout": 2700000
  }
}

```"# comfy-worker" 
