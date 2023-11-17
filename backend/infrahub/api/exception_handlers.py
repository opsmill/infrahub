from fastapi.responses import JSONResponse
from pydantic import ValidationError

from infrahub.exceptions import Error


async def generic_api_exception_handler(_, exc: Exception, http_code: int = 500) -> JSONResponse:
    """Generic API Exception handler."""
    if isinstance(exc, Error):
        if exc.HTTP_CODE:
            http_code = exc.HTTP_CODE
        messages = [str(exc.message) if exc.message else exc.DESCRIPTION]
    elif isinstance(exc, ValidationError):
        messages = [ed["msg"] for ed in exc.errors()]
    else:
        messages = [str(exc)]
    error_dict = {
        "data": None,
        "errors": [{"message": message, "extensions": {"code": http_code}} for message in messages],
    }

    return JSONResponse(status_code=http_code, content=error_dict)
