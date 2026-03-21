import asyncio
from typing import Dict

from fastapi import WebSocket


class SignalingState:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}


SIGNALING_STATE = SignalingState()
