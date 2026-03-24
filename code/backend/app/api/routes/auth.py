from typing import Optional

from fastapi import APIRouter, Form
from pydantic import BaseModel, Field

from app.services.auth_service import login_user, register_user, update_user_profile
from app.utils.response import success


router = APIRouter(prefix="/auth", tags=["auth"])


class UpdateProfileReq(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    email: Optional[str] = Field(default=None, max_length=128)


@router.post("/register")
def register(
    login_user_id: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(...),
    email: Optional[str] = Form(default=None),
):
    data = register_user(login_user_id, password, display_name, email)
    return success(data=data)


@router.post("/login")
def login(login_user_id: str = Form(...), password: str = Form(...)):
    data = login_user(login_user_id, password)
    return success(data=data)


@router.post("/profile")
def update_profile(req: UpdateProfileReq):
    data = update_user_profile(req.user_id, req.display_name, req.email)
    return success(data=data)
