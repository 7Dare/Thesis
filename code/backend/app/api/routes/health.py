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
        "focus_weights": os.getenv(
            "FOCUS_WEIGHTS",
            "/home/ryh/thesis/results/focus_cls_daisee_small_v1_gpu_b8_i192/weights/best.pt",
        ),
        "webrtc": get_webrtc_config(),
    }
    return success(data=data)
