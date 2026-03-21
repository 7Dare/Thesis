import asyncio
import os
import time
from typing import Dict, List, Optional

from fastapi import WebSocket

from app.services.room_service import leave_room_by_disconnect
from app.state.presence_state import PRESENCE_STATE
from app.state.signaling_state import SIGNALING_STATE


def _now() -> float:
    return time.time()


PRESENCE_TIMEOUT_SECONDS = int(os.getenv("PRESENCE_TIMEOUT_SECONDS", "60"))


class SignalingService:
    async def connect(self, room_id: str, user_id: str, websocket: WebSocket) -> List[str]:
        await websocket.accept()
        await self.cancel_pending_disconnect(room_id, user_id)
        async with SIGNALING_STATE.lock:
            room = SIGNALING_STATE.rooms.setdefault(room_id, {})
            peers = [uid for uid in room.keys() if uid != user_id]
            room[user_id] = websocket
        return peers

    async def disconnect(self, room_id: str, user_id: str) -> None:
        async with SIGNALING_STATE.lock:
            room = SIGNALING_STATE.rooms.get(room_id)
            if not room:
                return
            room.pop(user_id, None)
            if not room:
                SIGNALING_STATE.rooms.pop(room_id, None)

    async def send(self, room_id: str, user_id: str, payload: Dict) -> None:
        async with SIGNALING_STATE.lock:
            ws = SIGNALING_STATE.rooms.get(room_id, {}).get(user_id)
        if ws:
            await ws.send_json(payload)

    async def broadcast(self, room_id: str, payload: Dict, except_user_id: Optional[str] = None) -> None:
        async with SIGNALING_STATE.lock:
            peers = list(SIGNALING_STATE.rooms.get(room_id, {}).items())
        for uid, ws in peers:
            if except_user_id and uid == except_user_id:
                continue
            await ws.send_json(payload)

    async def close_room_connections(self, room_id: str, reason: str = "room_closed") -> None:
        async with SIGNALING_STATE.lock:
            peers = list(SIGNALING_STATE.rooms.get(room_id, {}).items())
            SIGNALING_STATE.rooms.pop(room_id, None)
        for _, ws in peers:
            try:
                await ws.close(code=4404, reason=reason)
            except Exception:
                pass

    async def schedule_disconnect(self, room_id: str, user_id: str, timeout_seconds: int = PRESENCE_TIMEOUT_SECONDS) -> None:
        key = (room_id, user_id)

        async with PRESENCE_STATE.lock:
            prev = PRESENCE_STATE.tasks.pop(key, None)
            PRESENCE_STATE.pending_disconnects[key] = _now() + float(timeout_seconds)

        if prev:
            prev.cancel()

        task = asyncio.create_task(self._run_disconnect_timer(room_id, user_id, timeout_seconds))
        async with PRESENCE_STATE.lock:
            PRESENCE_STATE.tasks[key] = task

    async def cancel_pending_disconnect(self, room_id: str, user_id: str) -> None:
        key = (room_id, user_id)
        async with PRESENCE_STATE.lock:
            task = PRESENCE_STATE.tasks.pop(key, None)
            PRESENCE_STATE.pending_disconnects.pop(key, None)
        if task:
            task.cancel()

    async def _run_disconnect_timer(self, room_id: str, user_id: str, timeout_seconds: int) -> None:
        key = (room_id, user_id)
        try:
            await asyncio.sleep(timeout_seconds)
            result = leave_room_by_disconnect(room_id, user_id)
            if result.get("status") == "closed":
                await self.broadcast(
                    room_id,
                    self.envelope("room_closed", room_id, user_id, {"reason": "disconnect_timeout"}),
                )
                await self.close_room_connections(room_id, reason="room_closed")
        except asyncio.CancelledError:
            return
        finally:
            async with PRESENCE_STATE.lock:
                PRESENCE_STATE.tasks.pop(key, None)
                PRESENCE_STATE.pending_disconnects.pop(key, None)

    def envelope(self, msg_type: str, room_id: str, from_user_id: str, payload: Optional[Dict] = None) -> Dict:
        return {
            "type": msg_type,
            "room_id": room_id,
            "from_user_id": from_user_id,
            "payload": payload or {},
            "ts": _now(),
        }


SIGNALING_SERVICE = SignalingService()
