import asyncio
from typing import Dict, Tuple


PresenceKey = Tuple[str, str]


class PresenceState:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.pending_disconnects: Dict[PresenceKey, float] = {}
        self.tasks: Dict[PresenceKey, asyncio.Task] = {}


PRESENCE_STATE = PresenceState()

