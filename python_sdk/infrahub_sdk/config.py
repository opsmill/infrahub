from typing import Any, Dict, Optional

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from infrahub_sdk.playback import JSONPlayback
from infrahub_sdk.recorder import JSONRecorder, NoRecorder, Recorder, RecorderType
from infrahub_sdk.types import AsyncRequester, RequesterTransport, SyncRequester
from infrahub_sdk.utils import get_branch, is_valid_url


class Config(pydantic.BaseSettings):
    address: str = pydantic.Field(
        default="http://localhost:8000",
        description="The URL to use when connecting to Infrahub.",
    )
    api_token: Optional[str] = pydantic.Field(
        default=None, description="API token for authentication against Infrahub."
    )
    username: Optional[str] = pydantic.Field(default=None, description="Username for accessing Infrahub", min_length=1)
    password: Optional[str] = pydantic.Field(default=None, description="Password for accessing Infrahub", min_length=1)
    recorder: RecorderType = pydantic.Field(
        default=RecorderType.NONE,
        description="Select builtin recorder for later replay.",
    )
    custom_recorder: Recorder = pydantic.Field(
        default_factory=NoRecorder.default,
        description="Provides a way to record responses from the Infrahub API",
    )
    default_branch: str = pydantic.Field(
        default="main", description="Default branch to target if not specified for each request."
    )
    default_branch_from_git: bool = pydantic.Field(
        default=False,
        description="Indicates if the default Infrahub branch to target should come from the active branch in the local Git repository.",
    )
    requester: Optional[AsyncRequester] = None
    timeout: int = pydantic.Field(default=10, description="Default connection timeout in seconds")
    transport: RequesterTransport = pydantic.Field(
        default=RequesterTransport.HTTPX,
        description="Set an alternate transport using a predefined option",
    )
    sync_requester: Optional[SyncRequester] = None

    class Config:
        env_prefix = "INFRAHUB_SDK_"
        case_sensitive = False
        validate_assignment = True

    @pydantic.root_validator(pre=True)
    @classmethod
    def validate_credentials_input(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        has_username = "username" in values
        has_password = "password" in values
        if has_username != has_password:
            raise ValueError("Both 'username' and 'password' needs to be set")
        return values

    @pydantic.root_validator(pre=True)
    @classmethod
    def set_custom_recorder(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values.get("recorder") == RecorderType.NONE and "custom_recorder" not in values:
            values["custom_recorder"] = NoRecorder()
        elif values.get("recorder") == RecorderType.JSON and "custom_recorder" not in values:
            values["custom_recorder"] = JSONRecorder()
        return values

    @pydantic.root_validator(pre=True)
    @classmethod
    def set_transport(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values.get("transport") == RequesterTransport.JSON:
            playback = JSONPlayback()
            if "requester" not in values:
                values["requester"] = playback.async_request
            if "sync_requester" not in values:
                values["sync_requester"] = playback.sync_request

        return values

    @pydantic.root_validator(pre=True)
    @classmethod
    def validate_mix_authentication_schemes(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values.get("password") and values.get("api_token"):
            raise ValueError("Unable to combine password with token based authentication")
        return values

    @pydantic.validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        if is_valid_url(value):
            return value

        raise ValueError("The configured address is not a valid url")

    @property
    def default_infrahub_branch(self) -> str:
        branch: Optional[str] = None
        if not self.default_branch_from_git:
            branch = self.default_branch

        return get_branch(branch=branch)

    @property
    def password_authentication(self) -> bool:
        if self.username:
            return True
        return False
