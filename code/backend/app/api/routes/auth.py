from typing import Optional

from fastapi import APIRouter, Form

from app.services.auth_service import login_user, register_user
from app.utils.response import success


router = APIRouter(prefix="/auth", tags=["auth"])


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
