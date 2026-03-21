from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from app.services.inference_service import get_snapshot_response, get_status, ingest_image
from app.utils.response import success


router = APIRouter(tags=["inference"])


@router.post("/ingest/frame")
async def ingest_frame(
    frame: UploadFile = File(...),
    room_id: str = Form(...),
    user_id: str = Form(...),
):
    raw = await frame.read()
    data = ingest_image(raw, room_id, user_id)
    return success(data=data)


@router.get("/status")
def status():
    data = get_status()
    return success(data=data)


@router.get("/snapshot")
def snapshot():
    data = get_snapshot_response()
    if data is None:
        raise HTTPException(status_code=404, detail="snapshot_not_found")
    return Response(content=data, media_type="image/jpeg")
