# Camera API

This module captures a local camera stream, runs YOLO inference, shows a local
window, and exposes a small HTTP API.

## Run

```bash
export YOLO_WEIGHTS=/home/ryh/thesis/results/yolo_demo3/weights/best.pt
export SOURCE=0
export DEVICE=0
export SHOW_WINDOW=1
export CONF=0.10
export SKIP_CLASS0=1
uvicorn app:APP --host 0.0.0.0 --port 8000
```

## Endpoints

- `GET /health`
- `GET /status` returns latest status + detections
- `GET /snapshot` returns latest annotated frame as JPEG

## Notes

- Set `SOURCE` to a device index (e.g. `0`) or a stream URL (e.g. `rtsp://...`).
- Press `q` in the window to stop the capture loop.
- If no GPU, set `DEVICE=cpu`.
- On WSL/headless servers, set `SHOW_WINDOW=0` to avoid Qt/xcb display errors.
- If detections are missing, lower `CONF` (e.g. `0.05`) and test `SKIP_CLASS0=0` for debugging.
