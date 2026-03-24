import os
import time
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
from fastapi import HTTPException
from ultralytics import YOLO

from app.state.runtime import STATE


YOLO_WEIGHTS = os.getenv("YOLO_WEIGHTS", "yolov8n.pt")
IMG_SIZE = int(os.getenv("IMG_SIZE", "640"))
CONF = float(os.getenv("CONF", "0.35"))
DEVICE = os.getenv("DEVICE", "cpu")
FOCUS_WEIGHTS = os.getenv(
    "FOCUS_WEIGHTS",
    "/home/ryh/thesis/results/focus_cls_daisee_small_v1_gpu_b8_i192/weights/best.pt",
)
FOCUS_IMG_SIZE = int(os.getenv("FOCUS_IMG_SIZE", "192"))
FOCUS_DEVICE = os.getenv("FOCUS_DEVICE", DEVICE)
PERSON_CLASS_ID = int(os.getenv("PERSON_CLASS_ID", "0"))
PHONE_CLASS_ID = int(os.getenv("PHONE_CLASS_ID", "67"))
PHONE_FRAMES_TRIGGER = int(os.getenv("PHONE_FRAMES_TRIGGER", "3"))
NO_PERSON_FRAMES_TRIGGER = int(os.getenv("NO_PERSON_FRAMES_TRIGGER", "2"))


def load_model() -> YOLO:
    with STATE.model_lock:
        if STATE.model is None:
            STATE.model = YOLO(YOLO_WEIGHTS)
    return STATE.model


def load_focus_model() -> YOLO | None:
    weights_path = Path(FOCUS_WEIGHTS)
    if not weights_path.exists():
        with STATE.lock:
            STATE.focus_enabled = False
        return None

    with STATE.focus_model_lock:
        if STATE.focus_model is None:
            STATE.focus_model = YOLO(str(weights_path))
        with STATE.lock:
            STATE.focus_enabled = True
    return STATE.focus_model


def _status_from_counts(person_count: int, phone_count: int) -> str:
    if person_count <= 0:
        return "no_person"
    if phone_count > 0:
        return "person_with_phone"
    return "person_no_phone"


def _stabilize_status(raw_status: str) -> str:
    if raw_status == "person_with_phone":
        STATE.phone_streak += 1
    else:
        STATE.phone_streak = 0

    if raw_status == "no_person":
        STATE.no_person_streak += 1
    else:
        STATE.no_person_streak = 0

    if STATE.phone_streak >= PHONE_FRAMES_TRIGGER:
        return "person_with_phone"
    if STATE.no_person_streak >= NO_PERSON_FRAMES_TRIGGER:
        return "no_person"
    if raw_status == "person_no_phone":
        return "person_no_phone"
    return STATE.stable_status


def _classify_focus(frame: np.ndarray, has_person: bool) -> Dict:
    if not has_person:
        return {"focus_label": "no_person", "focus_score": 0.0, "focus_enabled": False}

    model = load_focus_model()
    if model is None:
        return {"focus_label": "unavailable", "focus_score": 0.0, "focus_enabled": False}

    result = model.predict(
        source=frame,
        imgsz=FOCUS_IMG_SIZE,
        device=FOCUS_DEVICE,
        verbose=False,
    )[0]
    probs = getattr(result, "probs", None)
    if probs is None:
        return {"focus_label": "unknown", "focus_score": 0.0, "focus_enabled": True}

    top1_idx = int(probs.top1)
    top1_conf = float(probs.top1conf.item() if hasattr(probs.top1conf, "item") else probs.top1conf)
    names = getattr(result, "names", {}) or {}
    label = names.get(top1_idx, str(top1_idx))
    return {
        "focus_label": label,
        "focus_score": round(top1_conf, 4),
        "focus_enabled": True,
    }


def infer_frame(frame: np.ndarray) -> Dict:
    model = load_model()
    result = model.predict(source=frame, imgsz=IMG_SIZE, conf=CONF, device=DEVICE, verbose=False)[0]

    dets: List[Dict] = []
    person_count = 0
    phone_count = 0

    if result.boxes is not None:
        for box in result.boxes:
            cls_id = int(box.cls.item())
            score = float(box.conf.item())
            x1, y1, x2, y2 = map(float, box.xyxy[0].tolist())
            if cls_id == PERSON_CLASS_ID:
                person_count += 1
            elif cls_id == PHONE_CLASS_ID:
                phone_count += 1
            dets.append({"class_id": cls_id, "conf": score, "xyxy": [x1, y1, x2, y2]})

    raw_status = _status_from_counts(person_count, phone_count)
    stable_status = _stabilize_status(raw_status)
    focus = _classify_focus(frame, has_person=person_count > 0)

    annotated = frame.copy()
    for d in dets:
        x1, y1, x2, y2 = map(int, d["xyxy"])
        color = (0, 200, 0)
        label = f"cls={d['class_id']} {d['conf']:.2f}"
        if d["class_id"] == PERSON_CLASS_ID:
            label = f"person {d['conf']:.2f}"
        elif d["class_id"] == PHONE_CLASS_ID:
            label = f"phone {d['conf']:.2f}"
            color = (0, 140, 255)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(annotated, label, (x1, max(0, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)

    cv2.putText(
        annotated,
        f"status={stable_status} person={person_count} phone={phone_count}",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        annotated,
        f"focus={focus['focus_label']} score={focus['focus_score']:.2f}",
        (12, 56),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    now = time.time()
    with STATE.lock:
        STATE.annotated = annotated
        STATE.last_ts = now
        STATE.raw_status = raw_status
        STATE.stable_status = stable_status
        STATE.person_count = person_count
        STATE.phone_count = phone_count
        STATE.focus_label = str(focus["focus_label"])
        STATE.focus_score = float(focus["focus_score"])
        STATE.focus_enabled = bool(focus["focus_enabled"])

    return {
        "status": stable_status,
        "raw_status": raw_status,
        "has_person": person_count > 0,
        "using_phone": person_count > 0 and phone_count > 0,
        "person_count": person_count,
        "phone_count": phone_count,
        "focus_label": focus["focus_label"],
        "focus_score": focus["focus_score"],
        "focus_enabled": focus["focus_enabled"],
        "ts": now,
    }


def ingest_image(raw: bytes, room_id: str, user_id: str) -> Dict:
    if not raw:
        raise HTTPException(status_code=400, detail="empty_frame")
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="invalid_image")

    out = infer_frame(img)
    with STATE.lock:
        STATE.last_room_id = room_id
        STATE.last_user_id = user_id
    return {"room_id": room_id, "user_id": user_id, **out}


def get_status() -> Dict:
    with STATE.lock:
        return {
            "room_id": STATE.last_room_id,
            "user_id": STATE.last_user_id,
            "status": STATE.stable_status,
            "raw_status": STATE.raw_status,
            "has_person": STATE.person_count > 0,
            "using_phone": STATE.person_count > 0 and STATE.phone_count > 0,
            "person_count": STATE.person_count,
            "phone_count": STATE.phone_count,
            "focus_label": STATE.focus_label,
            "focus_score": STATE.focus_score,
            "focus_enabled": STATE.focus_enabled,
            "ts": STATE.last_ts,
        }


def get_snapshot_response():
    with STATE.lock:
        img = STATE.annotated
        if img is None:
            return None
        ok, buf = cv2.imencode(".jpg", img)
        if not ok:
            raise HTTPException(status_code=500, detail="snapshot_encode_failed")
    return buf.tobytes()
