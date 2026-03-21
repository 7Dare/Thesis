# Windows Camera Stream (Python)

Run this on Windows to expose the webcam as an MJPEG stream.

## Install

```bash
pip install opencv-python flask
```

## Run

```bash
python windows_camera_stream.py
```

Stream URL:
- `http://<windows_ip>:5000/video`

## Find Windows IP in WSL

From WSL:

```bash
cat /etc/resolv.conf | grep nameserver
```

Use that IP as `<windows_ip>`.
