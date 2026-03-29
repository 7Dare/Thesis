import asyncio
import os
import secrets
import threading
import time
import uuid
from typing import Dict, List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from ultralytics import YOLO


APP = FastAPI()


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _default_show_window() -> bool:
    return bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))


APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# YOLO Config
SOURCE = os.getenv("SOURCE", "0")
INPUT_MODE = os.getenv("INPUT_MODE", "push" if SOURCE.strip().lower() == "push" else "pull").strip().lower()
WEIGHTS = os.getenv(
    "YOLO_WEIGHTS",
    "/home/ryh/Thesis/results/yolo_demo3/weights/best.pt",
)
IMG_SIZE = int(os.getenv("IMG_SIZE", "640"))
CONF = float(os.getenv("CONF", "0.10"))
DEVICE = os.getenv("DEVICE", "0")  # set to "cpu" if needed
SHOW_WINDOW = _env_flag("SHOW_WINDOW", _default_show_window())
SKIP_CLASS0 = _env_flag("SKIP_CLASS0", True)

# Focus reminder config
REMINDER_COOLDOWN_SEC = float(os.getenv("REMINDER_COOLDOWN_SEC", "30"))
DISTRACTION_TRIGGER_SEC = float(os.getenv("DISTRACTION_TRIGGER_SEC", "8"))
PHONE_TRIGGER_SEC = float(os.getenv("PHONE_TRIGGER_SEC", "5"))
MAX_REMINDER_HISTORY = int(os.getenv("MAX_REMINDER_HISTORY", "20"))

# Class mapping (dataset defines 0 as "skip")
CLASS_NAMES = {
    1: "reading",
    2: "writing",
    3: "phone",
    4: "distracted",
    5: "sleeping",
}
PRIORITY = [3, 5, 4, 2, 1]  # highest priority first


class SharedState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.frame = None
        self.annotated = None
        self.detections: List[Dict] = []
        self.status = "unknown"
        self.last_ts = 0.0
        self.focused = False
        self.focus_score = 0.0
        self.reminder: Optional[str] = None
        self.reminder_level = "none"
        self.reminders: List[Dict] = []
        self.distraction_since: Optional[float] = None
        self.last_reminder_ts = 0.0


STATE = SharedState()
ROOM_LOCK = threading.Lock()
ROOMS: Dict[str, Dict] = {}
INVITES: Dict[str, Dict] = {}
MODEL_LOCK = threading.Lock()
MODEL: Optional[YOLO] = None


class CreateRoomReq(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    room_name: str = Field(default="专注自习室", min_length=1, max_length=120)
    duration_minutes: int = Field(default=60, ge=15, le=600)


class JoinRoomReq(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)


class LeaveRoomReq(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)


class InviteReq(BaseModel):
    inviter_user_id: str = Field(min_length=1, max_length=64)
    invitee_name: str = Field(default="学习同伴", min_length=1, max_length=64)
    expires_in_minutes: int = Field(default=120, ge=5, le=1440)


class JoinByInviteReq(BaseModel):
    invite_code: str = Field(min_length=4, max_length=32)
    user_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)


class UpdateDurationReq(BaseModel):
    duration_minutes: int = Field(ge=15, le=600)


def _now() -> float:
    return time.time()


def _status_from_dets(dets: List[Dict]) -> str:
    present = {d["class_id"] for d in dets}
    for cid in PRIORITY:
        if cid in present:
            return CLASS_NAMES[cid]
    return "no_target"


def _focus_assessment(dets: List[Dict], current_status: str) -> Dict[str, Optional[str]]:
    now = _now()
    labels = {d["class_name"] for d in dets}
    focused = "reading" in labels or "writing" in labels
    severe = "sleeping" in labels
    medium = "phone" in labels or "distracted" in labels or current_status == "no_target"
    reminder = None
    level = "none"
    score = 0.85 if focused else 0.55

    if severe:
        score = 0.1
    elif "phone" in labels:
        score = 0.25
    elif "distracted" in labels:
        score = 0.4
    elif current_status == "no_target":
        score = 0.35

    if focused:
        STATE.distraction_since = None
    else:
        if STATE.distraction_since is None:
            STATE.distraction_since = now
        distracted_for = now - STATE.distraction_since
        if severe and distracted_for >= DISTRACTION_TRIGGER_SEC:
            reminder = "检测到你可能在休息，建议调整坐姿并回到学习任务。"
            level = "high"
        elif "phone" in labels and distracted_for >= PHONE_TRIGGER_SEC:
            reminder = "检测到手机使用，建议切回学习界面保持专注。"
            level = "medium"
        elif medium and distracted_for >= DISTRACTION_TRIGGER_SEC:
            reminder = "你已短暂偏离学习区域，试着回到书桌前继续当前任务。"
            level = "low"

    if reminder and now - STATE.last_reminder_ts < REMINDER_COOLDOWN_SEC:
        reminder = None
        level = "none"

    if reminder:
        STATE.last_reminder_ts = now
        STATE.reminders.append(
            {
                "message": reminder,
                "level": level,
                "ts": now,
            }
        )
        if len(STATE.reminders) > MAX_REMINDER_HISTORY:
            STATE.reminders = STATE.reminders[-MAX_REMINDER_HISTORY:]

    return {
        "focused": focused,
        "score": round(score, 2),
        "reminder": reminder,
        "level": level,
    }


def _parse_source(raw: str):
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    return raw


def _load_model() -> YOLO:
    global MODEL
    with MODEL_LOCK:
        if MODEL is None:
            MODEL = YOLO(WEIGHTS)
    return MODEL


def _infer_frame(frame) -> Dict:
    model = _load_model()
    results = model.predict(
        source=frame,
        imgsz=IMG_SIZE,
        conf=CONF,
        device=DEVICE,
        verbose=False,
    )[0]

    dets = []
    if results.boxes is not None:
        for box in results.boxes:
            cls_id = int(box.cls.item())
            if SKIP_CLASS0 and cls_id == 0:
                continue
            det_conf = float(box.conf.item())
            x1, y1, x2, y2 = map(float, box.xyxy[0].tolist())
            dets.append(
                {
                    "class_id": cls_id,
                    "class_name": CLASS_NAMES.get(cls_id, "unknown"),
                    "conf": det_conf,
                    "xyxy": [x1, y1, x2, y2],
                }
            )

    status = _status_from_dets(dets)
    focus_info = _focus_assessment(dets, status)

    annotated = frame.copy()
    for d in dets:
        x1, y1, x2, y2 = map(int, d["xyxy"])
        label = f"{d['class_name']} {d['conf']:.2f}"
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(
            annotated,
            label,
            (x1, max(0, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )

    if focus_info["reminder"]:
        cv2.putText(
            annotated,
            str(focus_info["reminder"]),
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 165, 255),
            2,
            cv2.LINE_AA,
        )

    with STATE.lock:
        STATE.frame = frame
        STATE.annotated = annotated
        STATE.detections = dets
        STATE.status = status
        STATE.last_ts = time.time()
        STATE.focused = bool(focus_info["focused"])
        STATE.focus_score = float(focus_info["score"])
        STATE.reminder = focus_info["reminder"]
        STATE.reminder_level = str(focus_info["level"])

    return {
        "status": status,
        "detections": dets,
        "focus": {
            "focused": bool(focus_info["focused"]),
            "score": float(focus_info["score"]),
            "reminder": focus_info["reminder"],
            "level": str(focus_info["level"]),
        },
        "ts": STATE.last_ts,
    }


def _user_payload(user_id: str, display_name: str, role: str = "member") -> Dict:
    return {"user_id": user_id, "display_name": display_name, "role": role}


def _room_payload(room: Dict) -> Dict:
    now = _now()
    return {
        "room_id": room["room_id"],
        "room_name": room["room_name"],
        "host_user_id": room["host_user_id"],
        "duration_minutes": room["duration_minutes"],
        "started_at": room["started_at"],
        "ends_at": room["ends_at"],
        "remaining_seconds": max(0, int(room["ends_at"] - now)),
        "members": list(room["members"].values()),
    }


class CallSignalingManager:
    def __init__(self) -> None:
        self._connections: Dict[str, Dict[str, WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_id: str, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            room_map = self._connections.setdefault(room_id, {})
            room_map[user_id] = websocket

    async def disconnect(self, room_id: str, user_id: str) -> None:
        async with self._lock:
            room_map = self._connections.get(room_id, {})
            room_map.pop(user_id, None)
            if not room_map:
                self._connections.pop(room_id, None)

    async def send(self, room_id: str, user_id: str, payload: Dict) -> None:
        async with self._lock:
            ws = self._connections.get(room_id, {}).get(user_id)
        if ws:
            await ws.send_json(payload)

    async def broadcast(self, room_id: str, payload: Dict, except_user_id: Optional[str] = None) -> None:
        async with self._lock:
            users = list(self._connections.get(room_id, {}).items())
        for uid, ws in users:
            if except_user_id and uid == except_user_id:
                continue
            await ws.send_json(payload)


SIGNALING = CallSignalingManager()


def _run_loop() -> None:
    cap = cv2.VideoCapture(_parse_source(SOURCE))
    if not cap.isOpened():
        raise RuntimeError("camera_open_failed")

    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue

        _infer_frame(frame)

        if SHOW_WINDOW:
            with STATE.lock:
                annotated = STATE.annotated
            if annotated is not None:
                cv2.imshow("camera", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


@APP.on_event("startup")
def _startup() -> None:
    _load_model()
    if INPUT_MODE == "pull":
        t = threading.Thread(target=_run_loop, daemon=True)
        t.start()


@APP.get("/health")
def health() -> Dict:
    return {"ok": True, "input_mode": INPUT_MODE, "source": SOURCE}


@APP.post("/ingest/frame")
async def ingest_frame(
    frame: UploadFile = File(...),
    room_id: Optional[str] = Form(default=None),
    user_id: Optional[str] = Form(default=None),
) -> Dict:
    _ = (room_id, user_id)
    raw = await frame.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty_frame")
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="invalid_image")
    return _infer_frame(img)


@APP.get("/status")
def status() -> Dict:
    with STATE.lock:
        return {
            "status": STATE.status,
            "detections": STATE.detections,
            "ts": STATE.last_ts,
            "focus": {
                "focused": STATE.focused,
                "score": STATE.focus_score,
                "reminder": STATE.reminder,
                "level": STATE.reminder_level,
            },
        }


@APP.get("/snapshot")
def snapshot() -> Response:
    with STATE.lock:
        img = STATE.annotated
        if img is None:
            return Response(status_code=404)
        ok, buf = cv2.imencode(".jpg", img)
        if not ok:
            return Response(status_code=500)
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@APP.get("/focus")
def focus() -> Dict:
    with STATE.lock:
        return {
            "focused": STATE.focused,
            "score": STATE.focus_score,
            "status": STATE.status,
            "last_reminder": {
                "message": STATE.reminder,
                "level": STATE.reminder_level,
            },
            "reminders": list(STATE.reminders),
            "ts": STATE.last_ts,
        }


@APP.post("/rooms")
def create_room(req: CreateRoomReq) -> Dict:
    room_id = uuid.uuid4().hex[:8]
    now = _now()
    host = _user_payload(req.user_id, req.display_name, role="host")
    room = {
        "room_id": room_id,
        "room_name": req.room_name,
        "host_user_id": req.user_id,
        "duration_minutes": req.duration_minutes,
        "started_at": now,
        "ends_at": now + req.duration_minutes * 60,
        "members": {req.user_id: host},
        "created_at": now,
    }
    with ROOM_LOCK:
        ROOMS[room_id] = room
    return _room_payload(room)


@APP.get("/rooms/{room_id}")
def get_room(room_id: str) -> Dict:
    with ROOM_LOCK:
        room = ROOMS.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="room_not_found")
        return _room_payload(room)


@APP.post("/rooms/{room_id}/join")
def join_room(room_id: str, req: JoinRoomReq) -> Dict:
    now = _now()
    with ROOM_LOCK:
        room = ROOMS.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="room_not_found")
        if now > room["ends_at"]:
            raise HTTPException(status_code=410, detail="room_expired")
        role = "host" if req.user_id == room["host_user_id"] else "member"
        room["members"][req.user_id] = _user_payload(req.user_id, req.display_name, role=role)
        payload = _room_payload(room)
    return payload


@APP.post("/rooms/{room_id}/leave")
def leave_room(room_id: str, req: LeaveRoomReq) -> Dict:
    with ROOM_LOCK:
        room = ROOMS.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="room_not_found")
        room["members"].pop(req.user_id, None)
        if not room["members"]:
            ROOMS.pop(room_id, None)
            return {"room_id": room_id, "closed": True}
        if req.user_id == room["host_user_id"]:
            new_host = next(iter(room["members"]))
            room["host_user_id"] = new_host
            room["members"][new_host]["role"] = "host"
        return _room_payload(room)


@APP.post("/rooms/{room_id}/duration")
def update_room_duration(room_id: str, req: UpdateDurationReq) -> Dict:
    with ROOM_LOCK:
        room = ROOMS.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="room_not_found")
        room["duration_minutes"] = req.duration_minutes
        room["ends_at"] = room["started_at"] + req.duration_minutes * 60
        return _room_payload(room)


@APP.post("/rooms/{room_id}/invite")
def create_invite(room_id: str, req: InviteReq) -> Dict:
    with ROOM_LOCK:
        room = ROOMS.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="room_not_found")
        if req.inviter_user_id not in room["members"]:
            raise HTTPException(status_code=403, detail="inviter_not_in_room")
    code = secrets.token_urlsafe(6)
    expires_at = _now() + req.expires_in_minutes * 60
    invite = {
        "invite_code": code,
        "room_id": room_id,
        "invitee_name": req.invitee_name,
        "created_by": req.inviter_user_id,
        "expires_at": expires_at,
    }
    with ROOM_LOCK:
        INVITES[code] = invite
    return invite


@APP.post("/rooms/join-by-invite")
def join_by_invite(req: JoinByInviteReq) -> Dict:
    now = _now()
    with ROOM_LOCK:
        invite = INVITES.get(req.invite_code)
        if not invite:
            raise HTTPException(status_code=404, detail="invite_not_found")
        if now > invite["expires_at"]:
            INVITES.pop(req.invite_code, None)
            raise HTTPException(status_code=410, detail="invite_expired")
        room = ROOMS.get(invite["room_id"])
        if not room:
            raise HTTPException(status_code=404, detail="room_not_found")
        if now > room["ends_at"]:
            raise HTTPException(status_code=410, detail="room_expired")
        role = "host" if req.user_id == room["host_user_id"] else "member"
        room["members"][req.user_id] = _user_payload(req.user_id, req.display_name, role=role)
        return _room_payload(room)


@APP.websocket("/rooms/{room_id}/signal")
async def room_signal(room_id: str, websocket: WebSocket, user_id: str, display_name: str = "member") -> None:
    with ROOM_LOCK:
        room = ROOMS.get(room_id)
        if not room:
            await websocket.close(code=4404)
            return
        if user_id not in room["members"]:
            room["members"][user_id] = _user_payload(user_id, display_name, role="member")

    await SIGNALING.connect(room_id, user_id, websocket)
    await SIGNALING.broadcast(
        room_id,
        {
            "type": "peer_join",
            "room_id": room_id,
            "from_user_id": user_id,
            "display_name": display_name,
            "ts": _now(),
        },
        except_user_id=user_id,
    )
    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")
            target_user_id = msg.get("target_user_id")
            payload = {
                "type": msg_type,
                "room_id": room_id,
                "from_user_id": user_id,
                "payload": msg.get("payload", {}),
                "ts": _now(),
            }
            if msg_type in {"offer", "answer", "ice"} and target_user_id:
                await SIGNALING.send(room_id, str(target_user_id), payload)
            else:
                await SIGNALING.broadcast(room_id, payload, except_user_id=user_id)
    except WebSocketDisconnect:
        await SIGNALING.disconnect(room_id, user_id)
        await SIGNALING.broadcast(
            room_id,
            {
                "type": "peer_leave",
                "room_id": room_id,
                "from_user_id": user_id,
                "ts": _now(),
            },
            except_user_id=user_id,
        )
