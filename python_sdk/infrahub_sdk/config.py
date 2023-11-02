from typing import Any, Dict, Optional

from pydantic import BaseSettings, Field, root_validator, validator

from infrahub_sdk.playback import JSONPlayback
from infrahub_sdk.recorder import JSONRecorder, Recorder, RecorderType
from infrahub_sdk.types import AsyncRequester, RequesterTransport, SyncRequester
from infrahub_sdk.utils import is_valid_url


class Config(BaseSettings):
    address: str = Field(
        default="http://localhost:8000",
        description="The URL to use when connecting to Infrahub.",
    )
    api_token: Optional[str] = Field(default=None, description="API token for authentication against Infrahub.")
    username: Optional[str] = Field(default=None, description="Username for accessing Infrahub", min_length=1)
    password: Optional[str] = Field(default=None, description="Password for accessing Infrahub", min_length=1)
    recorder: RecorderType = Field(
        default=RecorderType.NONE,
        description="Select builtin recorder for later replay.",
    )
    custom_recorder: Optional[Recorder] = Field(
        default=None,
        description="Provides a way to record responses from the Infrahub API",
    )
    requester: Optional[AsyncRequester] = None
    timeout: int = Field(default=10, description="Default connection timeout in seconds")
    transport: RequesterTransport = Field(
        default=RequesterTransport.HTTPX,
        description="Set an alternate transport using a predefined option",
    )
    sync_requester: Optional[SyncRequester] = None

    class Config:
        env_prefix = "INFRAHUB_SDK_"
        case_sensitive = False
        validate_assignment = True

    @root_validator(pre=True)
    @classmethod
    def validate_credentials_input(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        has_username = "username" in values
        has_password = "password" in values
        if has_username != has_password:
            raise ValueError("Both 'username' and 'password' needs to be set")
        return values

    @root_validator(pre=True)
    @classmethod
    def set_custom_recorder(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values.get("recorder") == RecorderType.JSON and "custom_recorder" not in values:
            values["custom_recorder"] = JSONRecorder()
        return values

    @root_validator(pre=True)
    @classmethod
    def set_transport(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values.get("transport") == RequesterTransport.JSON:
            playback = JSONPlayback()
            if "requester" not in values:
                values["requester"] = playback.async_request
            if "sync_requester" not in values:
                values["sync_requester"] = playback.sync_request

        return values

    @root_validator(pre=True)
    @classmethod
    def validate_mix_authentication_schemes(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values.get("password") and values.get("api_token"):
            raise ValueError("Unable to combine password with token based authentication")
        return values

    @validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        if is_valid_url(value):
            return value

        raise ValueError("The configured address is not a valid url")

    @property
    def password_authentication(self) -> bool:
        if self.username:
            return True
        return False
