from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.chat_service import (
    get_room_conversation,
    list_room_messages,
    send_room_message,
    update_read_cursor,
)
from app.utils.response import success


router = APIRouter(tags=["chat"])


class SendMessageReq(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=2000)


class UpdateReadCursorReq(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    last_read_message_id: int = Field(ge=1)


@router.get("/rooms/{room_id}/chat/conversation")
def get_conversation_api(room_id: str, user_id: str = Query(..., min_length=1, max_length=64)):
    data = get_room_conversation(room_id, user_id)
    return success(data=data)


@router.post("/rooms/{room_id}/chat/messages")
def send_message_api(room_id: str, req: SendMessageReq):
    data = send_room_message(room_id, req.user_id, req.content)
    return success(data=data)


@router.get("/rooms/{room_id}/chat/messages")
def list_messages_api(
    room_id: str,
    user_id: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(default=20, ge=1, le=100),
    before_message_id: Optional[int] = Query(default=None, ge=1),
):
    data = list_room_messages(room_id, user_id, limit=limit, before_message_id=before_message_id)
    return success(data=data)


@router.post("/rooms/{room_id}/chat/read-cursor")
def update_read_cursor_api(room_id: str, req: UpdateReadCursorReq):
    data = update_read_cursor(room_id, req.user_id, req.last_read_message_id)
    return success(data=data)
