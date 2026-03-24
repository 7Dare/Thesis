import threading
from typing import Optional

from ultralytics import YOLO


class SharedState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.model_lock = threading.Lock()
        self.focus_model_lock = threading.Lock()
        self.model: Optional[YOLO] = None
        self.focus_model: Optional[YOLO] = None

        self.annotated = None
        self.last_ts = 0.0
        self.last_room_id: Optional[str] = None
        self.last_user_id: Optional[str] = None

        self.raw_status = "no_person"
        self.stable_status = "no_person"
        self.person_count = 0
        self.phone_count = 0
        self.focus_label = "unknown"
        self.focus_score = 0.0
        self.focus_enabled = False

        self.phone_streak = 0
        self.no_person_streak = 0


STATE = SharedState()
