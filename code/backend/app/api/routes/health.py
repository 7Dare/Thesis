import os
from pathlib import Path

from fastapi import APIRouter

from app.core.webrtc_config import get_webrtc_config
from app.utils.response import success


router = APIRouter(tags=["health"])
DEFAULT_FOCUS_WEIGHTS = (
    Path(__file__).resolve().parents[4] / "models" / "yolo" / "weights" / "best_model.pth"
)
DEFAULT_YOLO_WEIGHTS = (
    Path(__file__).resolve().parents[4] / "models" / "yolo" / "weights" / "yolov8n.pt"
)


@router.get("/health")
def health():
    data = {
        "ok": True,
        "weights": os.getenv("YOLO_WEIGHTS", str(DEFAULT_YOLO_WEIGHTS)),
        "focus_weights": os.getenv(
            "FOCUS_WEIGHTS",
            str(DEFAULT_FOCUS_WEIGHTS),
        ),
        "webrtc": get_webrtc_config(),
    }
    return success(data=data)
