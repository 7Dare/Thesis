import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
import torch
import torch.nn as nn
from fastapi import HTTPException
from torchvision import models
from ultralytics import YOLO

from app.state.runtime import STATE
from app.services.room_service import record_focus_sample


DEFAULT_FOCUS_WEIGHTS = (
    Path(__file__).resolve().parents[3] / "models" / "yolo" / "weights" / "best_model.pth"
)
DEFAULT_YOLO_WEIGHTS = (
    Path(__file__).resolve().parents[3] / "models" / "yolo" / "weights" / "yolov8n.pt"
)
YOLO_WEIGHTS = os.getenv("YOLO_WEIGHTS", str(DEFAULT_YOLO_WEIGHTS))
IMG_SIZE = int(os.getenv("IMG_SIZE", "640"))
CONF = float(os.getenv("CONF", "0.35"))
DEVICE = os.getenv("DEVICE", "cpu")
FOCUS_WEIGHTS = os.getenv(
    "FOCUS_WEIGHTS",
    str(DEFAULT_FOCUS_WEIGHTS),
)
FOCUS_IMG_SIZE = int(os.getenv("FOCUS_IMG_SIZE", "224"))
FOCUS_DEVICE = os.getenv("FOCUS_DEVICE", DEVICE)
FOCUS_DISTRACT_THRESHOLD = float(os.getenv("FOCUS_DISTRACT_THRESHOLD", "0.60"))
FOCUS_WINDOW_SECONDS = float(os.getenv("FOCUS_WINDOW_SECONDS", "3.0"))
FOCUS_WINDOW_DISTRACT_RATE = float(os.getenv("FOCUS_WINDOW_DISTRACT_RATE", "0.70"))
FOCUS_WEIGHT_ENGAGEMENT = float(os.getenv("FOCUS_WEIGHT_ENGAGEMENT", "0.60"))
FOCUS_WEIGHT_BOREDOM = float(os.getenv("FOCUS_WEIGHT_BOREDOM", "0.10"))
FOCUS_WEIGHT_DISENGAGEMENT = float(os.getenv("FOCUS_WEIGHT_DISENGAGEMENT", "0.15"))
FOCUS_WEIGHT_CONFUSION = float(os.getenv("FOCUS_WEIGHT_CONFUSION", "0.08"))
FOCUS_WEIGHT_FRUSTRATION = float(os.getenv("FOCUS_WEIGHT_FRUSTRATION", "0.07"))
FOCUS_SCORE_GAMMA = float(os.getenv("FOCUS_SCORE_GAMMA", "1.8"))
FOCUS_DISTRACT_PENALTY = float(os.getenv("FOCUS_DISTRACT_PENALTY", "0.22"))
PERSON_CLASS_ID = int(os.getenv("PERSON_CLASS_ID", "0"))
PHONE_CLASS_ID = int(os.getenv("PHONE_CLASS_ID", "67"))
PHONE_FRAMES_TRIGGER = int(os.getenv("PHONE_FRAMES_TRIGGER", "3"))
NO_PERSON_FRAMES_TRIGGER = int(os.getenv("NO_PERSON_FRAMES_TRIGGER", "2"))
IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32).view(1, 3, 1, 1)
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32).view(1, 3, 1, 1)


class FocusMultiTaskResNet18(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        backbone = models.resnet18(weights=None)
        d = backbone.fc.in_features
        backbone.fc = nn.Identity()
        self.backbone = backbone
        self.h_b = nn.Linear(d, 2)
        self.h_e = nn.Linear(d, 2)
        self.h_c = nn.Linear(d, 2)
        self.h_f = nn.Linear(d, 2)

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        feat = self.backbone(x)
        return {
            "boredom": self.h_b(feat),
            "engagement": self.h_e(feat),
            "confusion": self.h_c(feat),
            "frustration": self.h_f(feat),
        }


def _torch_device() -> torch.device:
    raw = str(FOCUS_DEVICE).strip().lower()
    if raw == "cpu" or not torch.cuda.is_available():
        return torch.device("cpu")
    if raw.isdigit():
        return torch.device(f"cuda:{raw}")
    return torch.device(raw)


def load_model() -> YOLO:
    with STATE.model_lock:
        if STATE.model is None:
            STATE.model = YOLO(YOLO_WEIGHTS)
    return STATE.model


def load_focus_model() -> nn.Module | None:
    weights_path = Path(FOCUS_WEIGHTS)
    if not weights_path.exists():
        with STATE.lock:
            STATE.focus_enabled = False
        return None

    with STATE.focus_model_lock:
        if STATE.focus_model is None:
            model = FocusMultiTaskResNet18()
            state = torch.load(weights_path, map_location="cpu", weights_only=False)
            if isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]
            if not isinstance(state, dict):
                raise RuntimeError("focus_weights_format_invalid")
            model.load_state_dict(state, strict=True)
            model.to(_torch_device())
            model.eval()
            STATE.focus_model = model
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


def _expand_box(x1: float, y1: float, x2: float, y2: float, w: int, h: int, ratio: float = 0.08) -> tuple[int, int, int, int]:
    bw = max(x2 - x1, 1.0)
    bh = max(y2 - y1, 1.0)
    pad_x = bw * ratio
    pad_y = bh * ratio
    return (
        max(0, int(x1 - pad_x)),
        max(0, int(y1 - pad_y)),
        min(w, int(x2 + pad_x)),
        min(h, int(y2 + pad_y)),
    )


def _select_person_crop(frame: np.ndarray, dets: List[Dict]) -> Optional[tuple[np.ndarray, tuple[int, int, int, int]]]:
    h, w = frame.shape[:2]
    person_boxes = [d for d in dets if d["class_id"] == PERSON_CLASS_ID]
    if not person_boxes:
        return None
    best = max(
        person_boxes,
        key=lambda d: max((d["xyxy"][2] - d["xyxy"][0]) * (d["xyxy"][3] - d["xyxy"][1]), 0.0),
    )
    x1, y1, x2, y2 = _expand_box(*best["xyxy"], w=w, h=h)
    if x2 <= x1 or y2 <= y1:
        return None
    return frame[y1:y2, x1:x2].copy(), (x1, y1, x2, y2)


def _preprocess_focus_crop(crop: np.ndarray) -> torch.Tensor:
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (FOCUS_IMG_SIZE, FOCUS_IMG_SIZE), interpolation=cv2.INTER_AREA)
    x = torch.from_numpy(resized).float().permute(2, 0, 1).unsqueeze(0) / 255.0
    return (x - IMAGENET_MEAN) / IMAGENET_STD


def _update_focus_window(room_id: str, user_id: str, now: float, distracted: bool) -> Dict:
    key = (room_id or "-", user_id or "-")
    with STATE.lock:
        window = STATE.focus_windows.setdefault(key, [])
        window.append((now, distracted))
        cutoff = now - FOCUS_WINDOW_SECONDS
        STATE.focus_windows[key] = [(ts, flag) for ts, flag in window if ts >= cutoff]
        kept = STATE.focus_windows[key]
        frames = len(kept)
        rate = (sum(1 for _, flag in kept if flag) / frames) if frames else 0.0
    return {
        "distraction_rate": round(rate, 4),
        "intervention_required": frames > 0 and rate >= FOCUS_WINDOW_DISTRACT_RATE,
        "focus_window_seconds": FOCUS_WINDOW_SECONDS,
        "focus_window_frames": frames,
    }


def _calibrate_focus_score(raw_score: float, distracted: bool, distraction_rate: float) -> float:
    raw = max(0.0, min(1.0, raw_score))
    # Non-linear stretching: push mid-score samples down to avoid clustering around ~0.7.
    calibrated = raw ** max(0.5, FOCUS_SCORE_GAMMA)
    if distracted:
        penalty = FOCUS_DISTRACT_PENALTY * (0.5 + 0.5 * max(0.0, min(1.0, distraction_rate)))
        calibrated -= penalty
    return max(0.0, min(1.0, calibrated))


def _compute_distraction_score(
    boredom: float,
    engagement: float,
    confusion: float,
    frustration: float,
) -> tuple[float, Dict[str, float]]:
    disengagement = max(0.0, min(1.0, 1.0 - engagement))
    weights = {
        "engagement": max(0.0, FOCUS_WEIGHT_ENGAGEMENT),
        "boredom": max(0.0, FOCUS_WEIGHT_BOREDOM),
        "disengagement": max(0.0, FOCUS_WEIGHT_DISENGAGEMENT),
        "confusion": max(0.0, FOCUS_WEIGHT_CONFUSION),
        "frustration": max(0.0, FOCUS_WEIGHT_FRUSTRATION),
    }
    weight_sum = sum(weights.values())
    if weight_sum <= 1e-6:
        weights = {
            "engagement": 0.60,
            "boredom": 0.10,
            "disengagement": 0.15,
            "confusion": 0.08,
            "frustration": 0.07,
        }
        weight_sum = 1.0

    normalized_weights = {name: value / weight_sum for name, value in weights.items()}
    focus_score_raw = (
        engagement * normalized_weights["engagement"]
        + (1.0 - boredom) * normalized_weights["boredom"]
        + (1.0 - disengagement) * normalized_weights["disengagement"]
        + (1.0 - confusion) * normalized_weights["confusion"]
        + (1.0 - frustration) * normalized_weights["frustration"]
    )
    distraction_score = 1.0 - focus_score_raw
    return max(0.0, min(1.0, distraction_score)), {
        "disengagement_prob": round(disengagement, 4),
        "weight_engagement": round(normalized_weights["engagement"], 4),
        "weight_boredom": round(normalized_weights["boredom"], 4),
        "weight_disengagement": round(normalized_weights["disengagement"], 4),
        "weight_confusion": round(normalized_weights["confusion"], 4),
        "weight_frustration": round(normalized_weights["frustration"], 4),
        "focus_score_raw_weighted": round(max(0.0, min(1.0, focus_score_raw)), 4),
    }


def _classify_focus(crop: Optional[np.ndarray], room_id: str, user_id: str, now: float) -> Dict:
    if crop is None:
        return {
            "focus_label": "no_person",
            "focus_score": 0.0,
            "focus_value": 0.0,
            "focus_enabled": False,
            "distracted": False,
            "distraction_rate": 0.0,
            "intervention_required": False,
            "focus_window_seconds": FOCUS_WINDOW_SECONDS,
            "focus_window_frames": 0,
            "focus_detail": {},
        }

    model = load_focus_model()
    if model is None:
        return {
            "focus_label": "unavailable",
            "focus_score": 0.0,
            "focus_value": 0.0,
            "focus_enabled": False,
            "distracted": False,
            "distraction_rate": 0.0,
            "intervention_required": False,
            "focus_window_seconds": FOCUS_WINDOW_SECONDS,
            "focus_window_frames": 0,
            "focus_detail": {},
        }

    device = _torch_device()
    x = _preprocess_focus_crop(crop).to(device)
    with torch.no_grad():
        out = model(x)
        probs = {name: torch.softmax(logits, dim=1)[0].detach().cpu() for name, logits in out.items()}

    boredom = float(probs["boredom"][1])
    engagement = float(probs["engagement"][1])
    confusion = float(probs["confusion"][1])
    frustration = float(probs["frustration"][1])
    distraction_score, score_detail = _compute_distraction_score(
        boredom,
        engagement,
        confusion,
        frustration,
    )
    distracted = distraction_score >= FOCUS_DISTRACT_THRESHOLD
    window = _update_focus_window(room_id, user_id, now, distracted)
    label = "distracted" if window["intervention_required"] else ("suspected_distracted" if distracted else "focused")
    raw_focus_score = max(0.0, min(1.0, 1.0 - distraction_score))
    calibrated_score = _calibrate_focus_score(
        raw_focus_score,
        distracted=distracted,
        distraction_rate=float(window["distraction_rate"]),
    )
    focus_score = raw_focus_score
    return {
        "focus_label": label,
        "focus_score": round(focus_score, 4),
        "focus_value": round(focus_score, 4),
        "focus_enabled": True,
        "distracted": distracted,
        **window,
        "focus_detail": {
            "boredom_prob": round(boredom, 4),
            "engagement_prob": round(engagement, 4),
            "confusion_prob": round(confusion, 4),
            "frustration_prob": round(frustration, 4),
            "distraction_score": round(distraction_score, 4),
            "raw_focus_score": round(raw_focus_score, 4),
            "calibrated_focus_score": round(calibrated_score, 4),
            **score_detail,
        },
    }


def infer_frame(frame: np.ndarray, room_id: str, user_id: str) -> Dict:
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
    now = time.time()
    crop_result = _select_person_crop(frame, dets)
    focus_crop = crop_result[0] if crop_result else None
    focus_box = crop_result[1] if crop_result else None
    focus = _classify_focus(focus_crop, room_id=room_id, user_id=user_id, now=now)

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
    if focus_box is not None:
        x1, y1, x2, y2 = focus_box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (80, 220, 255), 2)
        cv2.putText(annotated, "focus crop", (x1, min(annotated.shape[0] - 6, y2 + 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (80, 220, 255), 2, cv2.LINE_AA)

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
        f"focus={focus['focus_label']} score={focus['focus_score']:.2f} distract_rate={focus['distraction_rate']:.2f}",
        (12, 56),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    with STATE.lock:
        STATE.annotated = annotated
        STATE.last_ts = now
        STATE.raw_status = raw_status
        STATE.stable_status = stable_status
        STATE.person_count = person_count
        STATE.phone_count = phone_count
        STATE.focus_label = str(focus["focus_label"])
        STATE.focus_score = float(focus["focus_score"])
        STATE.focus_value = float(focus["focus_value"])
        STATE.raw_focus_score = float(focus["focus_detail"].get("raw_focus_score", 0.0))
        STATE.focus_enabled = bool(focus["focus_enabled"])
        STATE.distracted = bool(focus["distracted"])
        STATE.distraction_rate = float(focus["distraction_rate"])
        STATE.intervention_required = bool(focus["intervention_required"])
        STATE.focus_window_seconds = float(focus["focus_window_seconds"])
        STATE.focus_window_frames = int(focus["focus_window_frames"])

    return {
        "status": stable_status,
        "raw_status": raw_status,
        "has_person": person_count > 0,
        "using_phone": person_count > 0 and phone_count > 0,
        "person_count": person_count,
        "phone_count": phone_count,
        "focus_label": focus["focus_label"],
        "focus_score": focus["focus_score"],
        "focus_value": focus["focus_value"],
        "raw_focus_score": focus["focus_detail"].get("raw_focus_score", 0.0),
        "focus_enabled": focus["focus_enabled"],
        "distracted": focus["distracted"],
        "distraction_rate": focus["distraction_rate"],
        "intervention_required": focus["intervention_required"],
        "focus_window_seconds": focus["focus_window_seconds"],
        "focus_window_frames": focus["focus_window_frames"],
        "focus_detail": focus["focus_detail"],
        "ts": now,
    }


def ingest_image(raw: bytes, room_id: str, user_id: str) -> Dict:
    if not raw:
        raise HTTPException(status_code=400, detail="empty_frame")
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="invalid_image")

    out = infer_frame(img, room_id=room_id, user_id=user_id)
    record_focus_sample(room_id, user_id, out)
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
            "focus_value": STATE.focus_value,
            "raw_focus_score": STATE.raw_focus_score,
            "focus_enabled": STATE.focus_enabled,
            "distracted": STATE.distracted,
            "distraction_rate": STATE.distraction_rate,
            "intervention_required": STATE.intervention_required,
            "focus_window_seconds": STATE.focus_window_seconds,
            "focus_window_frames": STATE.focus_window_frames,
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
