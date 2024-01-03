from json import loads
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from infrahub.api.exception_handlers import generic_api_exception_handler
from infrahub.exceptions import Error


class ModelForTesting(BaseModel):
    field_1: Optional[str] = Field(default=None, validate_default=True)
    field_2: Optional[str] = Field(default=None, validate_default=True)

    @field_validator("field_1")
    @classmethod
    def always_fail_1(cls, values: Any):
        raise ValueError("this is the error message")

    @field_validator("field_2")
    @classmethod
    def always_fail_2(cls, values: Any):
        raise ValueError("another error message")


class MockError(Error):
    HTTP_CODE = 418
    DESCRIPTION = "the teapot error"

    def __init__(self, message: Optional[str]):
        self.message = message


class TestAPIExceptionHandler:
    def setup_method(self):
        self.error_message = "this is the error message"

    async def test_plain_exception_error(self):
        exception = ValueError(self.error_message)

        error_response = await generic_api_exception_handler(None, exception)

        error_dict = loads(error_response.body.decode())
        assert error_dict["errors"] == [{"message": self.error_message, "extensions": {"code": 500}}]

    async def test_pydantic_validation_error(self):
        error_message_2 = "another error message"
        exception = None
        try:
            ModelForTesting(field_1="abc")
        except ValidationError as exc:
            exception = exc

        error_response = await generic_api_exception_handler(None, exception, http_code=400)

        error_dict = loads(error_response.body.decode())
        assert {"message": f"Value error, {self.error_message}", "extensions": {"code": 400}} in error_dict["errors"]
        assert {"message": f"Value error, {error_message_2}", "extensions": {"code": 400}} in error_dict["errors"]
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
