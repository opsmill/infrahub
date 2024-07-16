from typing import Optional

from pydantic import BaseModel, ValidationError, field_validator
from ujson import loads

from infrahub.api.exception_handlers import generic_api_exception_handler
from infrahub.exceptions import Error


class ModelForTesting(BaseModel):
    field_1: Optional[str] = None
    field_2: str

    @field_validator("field_1", mode="before")
    @classmethod
    def always_fail(cls, value: Optional[str] = None) -> str:
        raise ValueError("this is the error message")

    @field_validator("field_2", mode="before")
    @classmethod
    def always_fail_more(cls, value: Optional[str] = None) -> str:
        raise ValueError("another error message")


class MockError(Error):
    HTTP_CODE = 418
    DESCRIPTION = "the teapot error"

    def __init__(self, message: Optional[str]):
        self.message = message or ""


class TestAPIExceptionHandler:
    def setup_method(self):
        self.error_message = "Value error, this is the error message"

    async def test_plain_exception_error(self):
        exception = ValueError(self.error_message)

        error_response = await generic_api_exception_handler(None, exception)

        error_dict = loads(error_response.body.decode())
        assert error_dict["errors"] == [{"message": self.error_message, "extensions": {"code": 500}}]

    async def test_pydantic_validation_error(self):
        error_message_2 = "Value error, another error message"
        exception = Error()
        try:
            ModelForTesting(field_1="abc", field_2="def")
        except ValidationError as exc:
            exception = exc

        error_response = await generic_api_exception_handler(None, exception, http_code=400)

        error_dict = loads(error_response.body.decode())
        assert {"message": self.error_message, "extensions": {"code": 400}} in error_dict["errors"]
        assert {"message": error_message_2, "extensions": {"code": 400}} in error_dict["errors"]
        assert len(error_dict) == 2

    async def test_infrahub_api_error(self):
        exception = MockError(self.error_message)

        error_response = await generic_api_exception_handler(None, exception)

        error_dict = loads(error_response.body.decode())
        assert error_dict["errors"] == [{"message": self.error_message, "extensions": {"code": 418}}]

    async def test_infrahub_api_error_default_message(self):
        exception = MockError(None)

        error_response = await generic_api_exception_handler(None, exception)

        error_dict = loads(error_response.body.decode())
        assert error_dict["errors"] == [{"message": "the teapot error", "extensions": {"code": 418}}]

    async def test_infrahub_api_error_code_override(self):
        exception = MockError(None)

        error_response = await generic_api_exception_handler(None, exception, http_code=500)

        error_dict = loads(error_response.body.decode())
        assert error_dict["errors"] == [{"message": "the teapot error", "extensions": {"code": 418}}]
