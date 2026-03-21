from fastapi import APIRouter, Query

from app.services.user_stats_service import get_user_study_calendar
from app.utils.response import success


router = APIRouter(tags=["user-stats"])


@router.get("/users/{user_id}/study-calendar")
def user_study_calendar_api(user_id: str, days: int = Query(default=365, ge=30, le=730)):
    data = get_user_study_calendar(user_id=user_id, days=days)
    return success(data=data)

