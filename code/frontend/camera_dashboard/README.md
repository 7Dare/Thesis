# Camera Dashboard

Static dashboard for:

1. WebRTC room-based audio+video mesh calling.
2. YOLO frame upload + status display.

## Run

```bash
cd /home/ryh/thesis/code/frontend/camera_dashboard
python3 -m http.server 8080
```

Open `http://localhost:8080`.

## Workflow

1. Fill `API_BASE`, `room_id`, `user_id`, `display_name`.
2. Click `加入房间`.
3. Browser will request camera + microphone permissions.
4. Mic is muted by default, click `开麦` to unmute.
5. Local frames are uploaded every ~700ms for YOLO inference.

## Notes

- Current ICE default uses public STUN (`stun:stun.l.google.com:19302`).
- For cross-network reliability, configure TURN on backend and expose it via `/health` -> `data.webrtc.iceServers`.
- Mesh topology is recommended for small rooms (2-6 users).
