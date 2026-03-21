import os

from fastapi import APIRouter

from app.core.webrtc_config import get_webrtc_config
from app.utils.response import success


router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    data = {
        "ok": True,
        "weights": os.getenv("YOLO_WEIGHTS", "yolov8n.pt"),
        "webrtc": get_webrtc_config(),
    }
    return success(data=data)
