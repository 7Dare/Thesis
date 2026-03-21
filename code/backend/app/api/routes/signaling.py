from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.room_service import ensure_room_member_for_signal
from app.services.signaling_service import SIGNALING_SERVICE


router = APIRouter(tags=["signaling"])


@router.websocket("/rooms/{room_id}/signal")
async def room_signal(room_id: str, websocket: WebSocket, user_id: str, display_name: str = "member") -> None:
    if not user_id.strip():
        await websocket.close(code=4400, reason="user_id_required")
        return

    check = ensure_room_member_for_signal(room_id, user_id)
    if check == "not_room_member":
        await websocket.close(code=4403, reason="not_room_member")
        return
    if check == "room_not_found_or_closed":
        await websocket.close(code=4404, reason="room_not_found_or_closed")
        return

    peers = await SIGNALING_SERVICE.connect(room_id, user_id, websocket)

    for peer_id in peers:
        await SIGNALING_SERVICE.send(
            room_id,
            user_id,
            SIGNALING_SERVICE.envelope(
                "peer_join",
                room_id,
                peer_id,
                {"display_name": "member"},
            ),
        )

    await SIGNALING_SERVICE.broadcast(
        room_id,
        SIGNALING_SERVICE.envelope(
            "peer_join",
            room_id,
            user_id,
            {"display_name": display_name},
        ),
        except_user_id=user_id,
    )

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = str(msg.get("type", "")).strip()
            target_user_id = str(msg.get("target_user_id", "")).strip()
            payload = msg.get("payload", {})

            if msg_type not in {"offer", "answer", "ice", "peer_ping"}:
                await websocket.send_json(
                    SIGNALING_SERVICE.envelope(
                        "signal_error",
                        room_id,
                        user_id,
                        {"code": "unsupported_signal_type", "message": "unsupported_signal_type"},
                    )
                )
                continue

            out = SIGNALING_SERVICE.envelope(msg_type, room_id, user_id, payload if isinstance(payload, dict) else {})

            if msg_type in {"offer", "answer", "ice"}:
                if not target_user_id:
                    await websocket.send_json(
                        SIGNALING_SERVICE.envelope(
                            "signal_error",
                            room_id,
                            user_id,
                            {"code": "target_user_id_required", "message": "target_user_id_required"},
                        )
                    )
                    continue
                await SIGNALING_SERVICE.send(room_id, target_user_id, out)
            else:
                await SIGNALING_SERVICE.broadcast(room_id, out, except_user_id=user_id)
    except WebSocketDisconnect:
        await SIGNALING_SERVICE.disconnect(room_id, user_id)
        await SIGNALING_SERVICE.broadcast(
            room_id,
            SIGNALING_SERVICE.envelope("peer_leave", room_id, user_id, {}),
            except_user_id=user_id,
        )
        await SIGNALING_SERVICE.schedule_disconnect(room_id, user_id)
