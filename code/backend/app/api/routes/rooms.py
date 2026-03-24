from pydantic import BaseModel, Field
from fastapi import APIRouter, Query

from app.services.room_service import (
    check_room_resumable,
    close_room,
    create_room,
    get_current_active_room,
    get_room,
    get_room_study_time,
    join_by_invite,
    leave_room,
)
from app.services.signaling_service import SIGNALING_SERVICE
from app.utils.response import success


router = APIRouter(tags=["rooms"])


class CreateRoomReq(BaseModel):
    host_user_id: str = Field(min_length=1, max_length=64)
    room_name: str = Field(default="自习室", min_length=1, max_length=120)
    duration_minutes: int = Field(default=120, ge=1, le=1440)


class JoinByInviteReq(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    invite_code: str = Field(min_length=1, max_length=32)
    display_name: str = Field(default="member", min_length=1, max_length=64)


class LeaveReq(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)


class CloseReq(BaseModel):
    host_user_id: str = Field(min_length=1, max_length=64)


@router.post("/rooms")
def create_room_api(req: CreateRoomReq):
    data = create_room(req.host_user_id, req.room_name, req.duration_minutes)
    return success(data=data)


@router.post("/rooms/join-by-invite")
def join_by_invite_api(req: JoinByInviteReq):
    data = join_by_invite(req.user_id, req.invite_code, req.display_name)
    return success(data=data)


@router.get("/rooms/active/current")
def current_active_room_api(user_id: str = Query(min_length=1, max_length=64)):
    data = get_current_active_room(user_id)
    return success(data=data)


@router.post("/rooms/{room_id}/leave")
def leave_room_api(room_id: str, req: LeaveReq):
    data = leave_room(room_id, req.user_id)
    return success(data=data)


@router.post("/rooms/{room_id}/close")
async def close_room_api(room_id: str, req: CloseReq):
    data = close_room(room_id, req.host_user_id)
    await SIGNALING_SERVICE.broadcast(
        room_id,
        SIGNALING_SERVICE.envelope("room_closed", room_id, req.host_user_id, {"reason": "host_closed"}),
    )
    await SIGNALING_SERVICE.close_room_connections(room_id, reason="room_closed")
    return success(data=data)


@router.get("/rooms/{room_id}")
def get_room_api(room_id: str):
    data = get_room(room_id)
    return success(data=data)


@router.get("/rooms/{room_id}/resume-check")
def resume_check_api(room_id: str, user_id: str = Query(min_length=1, max_length=64)):
    data = check_room_resumable(room_id, user_id)
    return success(data=data)


@router.get("/rooms/{room_id}/study-time")
def room_study_time_api(room_id: str, user_id: str = Query(min_length=1, max_length=64)):
    data = get_room_study_time(room_id, user_id)
    return success(data=data)
