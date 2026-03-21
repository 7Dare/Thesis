from typing import Any, Optional, Union


def success(data: Any = None, message: str = "ok") -> dict:
    return {
        "code": 0,
        "message": message,
        "data": data,
    }


def error(code: Union[str, int], message: str, data: Optional[Any] = None) -> dict:
    return {
        "code": str(code),
        "message": message,
        "data": data,
    }
