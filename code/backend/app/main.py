from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.inference import router as inference_router
from app.api.routes.rooms import router as rooms_router
from app.api.routes.signaling import router as signaling_router
from app.api.routes.user_stats import router as user_stats_router
from app.core.error_codes import get_error_message
from app.services.inference_service import load_focus_model, load_model
from app.utils.response import error


APP = FastAPI(title="Study Monitor API")
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

APP.include_router(health_router)
APP.include_router(auth_router)
APP.include_router(rooms_router)
APP.include_router(chat_router)
APP.include_router(inference_router)
APP.include_router(signaling_router)
APP.include_router(user_stats_router)


@APP.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    code = exc.detail if isinstance(exc.detail, str) and exc.detail else "http_error"
    message = get_error_message(code)
    return JSONResponse(
        status_code=exc.status_code,
        content=error(code=code, message=message, data=None),
    )


@APP.exception_handler(Exception)
async def generic_exception_handler(_: Request, __: Exception):
    code = "internal_server_error"
    message = get_error_message(code)
    return JSONResponse(
        status_code=500,
        content=error(code=code, message=message, data=None),
    )


@APP.on_event("startup")
def _startup() -> None:
    load_model()
    load_focus_model()
