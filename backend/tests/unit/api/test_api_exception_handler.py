from typing import Any

from pydantic import BaseModel, ValidationError, field_validator
from starlette.responses import JSONResponse
from ujson import loads

from infrahub.api.exception_handlers import generic_api_exception_handler
from infrahub.exceptions import Error


def get_response_body(response: JSONResponse) -> dict[str, Any]:
    """Extract and decode response body as JSON dict."""
    body = response.body
    assert isinstance(body, bytes)
    return loads(body.decode())


class ModelForTesting(BaseModel):
    field_1: str | None = None
    field_2: str

    @field_validator("field_1", mode="before")
    @classmethod
    def always_fail(cls, value: str | None = None) -> str:
        raise ValueError("this is the error message")

    @field_validator("field_2", mode="before")
    @classmethod
    def always_fail_more(cls, value: str | None = None) -> str:
        raise ValueError("another error message")


class MockError(Error):
    HTTP_CODE = 418
    DESCRIPTION = "the teapot error"

    def __init__(self, message: str | None) -> None:
        self.message = message or ""


class TestAPIExceptionHandler:
    def setup_method(self) -> None:
        self.error_message = "Value error, this is the error message"

    async def test_plain_exception_error(self) -> None:
        exception = ValueError(self.error_message)

        error_response = await generic_api_exception_handler(None, exception)

        error_dict = get_response_body(error_response)
        assert error_dict["errors"] == [{"message": self.error_message, "extensions": {"code": 500}}]

    async def test_pydantic_validation_error(self) -> None:
        error_message_2 = "Value error, another error message"
        exception: ValidationError | None = None
        try:
            ModelForTesting(field_1="abc", field_2="def")
        except ValidationError as exc:
            exception = exc

        assert exception is not None
        error_response = await generic_api_exception_handler(None, exception, http_code=400)

        error_dict = get_response_body(error_response)
        assert {"message": self.error_message, "extensions": {"code": 400}} in error_dict["errors"]
        assert {"message": error_message_2, "extensions": {"code": 400}} in error_dict["errors"]
        assert len(error_dict) == 2

    async def test_infrahub_api_error(self) -> None:
        exception = MockError(self.error_message)

        error_response = await generic_api_exception_handler(None, exception)

        error_dict = get_response_body(error_response)
        assert error_dict["errors"] == [{"message": self.error_message, "extensions": {"code": 418}}]

    async def test_infrahub_api_error_default_message(self) -> None:
        exception = MockError(None)

        error_response = await generic_api_exception_handler(None, exception)

        error_dict = get_response_body(error_response)
        assert error_dict["errors"] == [{"message": "the teapot error", "extensions": {"code": 418}}]

    async def test_infrahub_api_error_code_override(self) -> None:
        exception = MockError(None)

        error_response = await generic_api_exception_handler(None, exception, http_code=500)

        error_dict = get_response_body(error_response)
        assert error_dict["errors"] == [{"message": "the teapot error", "extensions": {"code": 418}}]
