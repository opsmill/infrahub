from typing import Any

import logging
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from infrahub.exceptions import Error


async def generic_api_exception_handler(_: Any, exc: Exception, http_code: int = 500) -> JSONResponse:
    """Generic API Exception handler."""
    if isinstance(exc, Error):
        if exc.HTTP_CODE:
            http_code = exc.HTTP_CODE
        if isinstance(exc.errors, list):
            messages = exc.errors
        else:
            messages = [str(exc.message) if exc.message else exc.DESCRIPTION]
    elif isinstance(exc, ValidationError):
        messages = [ed["msg"] for ed in exc.errors()]
    else:
        # Log the exception for internal diagnostics; do not expose details to the user
        logging.exception("Unhandled exception in generic API exception handler:")
        messages = ["An internal error has occurred."]
    error_dict = {
        "data": None,
        "errors": [{"message": message, "extensions": {"code": http_code}} for message in messages],
    }

    return JSONResponse(status_code=http_code, content=error_dict)
