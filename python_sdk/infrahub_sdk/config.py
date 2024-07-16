from typing import Any, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

from infrahub_sdk.constants import InfrahubClientMode
from infrahub_sdk.playback import JSONPlayback
from infrahub_sdk.recorder import JSONRecorder, NoRecorder, Recorder, RecorderType
from infrahub_sdk.types import AsyncRequester, InfrahubLoggers, RequesterTransport, SyncRequester
from infrahub_sdk.utils import get_branch, is_valid_url


class ProxyMountsConfig(BaseSettings):
    model_config = SettingsConfigDict(populate_by_name=True)
    http: Optional[str] = Field(
        default=None,
        description="Proxy for HTTP requests",
        alias="http://",
        validation_alias="INFRAHUB_PROXY_MOUNTS_HTTP",
    )
    https: Optional[str] = Field(
        default=None,
        description="Proxy for HTTPS requests",
        alias="https://",
        validation_alias="INFRAHUB_PROXY_MOUNTS_HTTPS",
    )

    @property
    def is_set(self) -> bool:
        return self.http is not None or self.https is not None


class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_", validate_assignment=True)
    address: str = Field(default="http://localhost:8000", description="The URL to use when connecting to Infrahub.")
    api_token: Optional[str] = Field(default=None, description="API token for authentication against Infrahub.")
    echo_graphql_queries: bool = Field(
        default=False, description="If set the GraphQL query and variables will be echoed to the screen"
    )
    username: Optional[str] = Field(default=None, description="Username for accessing Infrahub", min_length=1)
    password: Optional[str] = Field(default=None, description="Password for accessing Infrahub", min_length=1)
    default_branch: str = Field(
        default="main", description="Default branch to target if not specified for each request."
    )
    default_branch_from_git: bool = Field(
        default=False,
        description="Indicates if the default Infrahub branch to target should come from the active branch in the local Git repository.",
    )
    identifier: Optional[str] = Field(default=None, description="Tracker identifier")
    insert_tracker: bool = Field(default=False, description="Insert a tracker on queries to the server")
    max_concurrent_execution: int = Field(default=5, description="Max concurrent execution in batch mode")
    mode: InfrahubClientMode = Field(default=InfrahubClientMode.DEFAULT, description="Default mode for the client")
    pagination_size: int = Field(default=50, description="Page size for queries to the server")
    retry_delay: int = Field(default=5, description="Number of seconds to wait until attempting a retry.")
    retry_on_failure: bool = Field(default=False, description="Retry operation in case of failure")
    timeout: int = Field(default=10, description="Default connection timeout in seconds")
    transport: RequesterTransport = Field(
        default=RequesterTransport.HTTPX, description="Set an alternate transport using a predefined option"
    )
    proxy: Optional[str] = Field(default=None, description="Proxy address")
    proxy_mounts: ProxyMountsConfig = Field(default=ProxyMountsConfig(), description="Proxy mounts configuration")
    update_group_context: bool = Field(default=False, description="Update GraphQL query groups")
    tls_insecure: bool = Field(
        default=False,
        description="""
    Indicates if TLS certificates are verified.
    Enabling this option will disable: CA verification, expiry date verification, hostname verification).
    Can be useful to test with self-signed certificates.""",
    )
    tls_ca_file: Optional[str] = Field(default=None, description="File path to CA cert or bundle in PEM format")

    @model_validator(mode="before")
    @classmethod
    def validate_credentials_input(cls, values: dict[str, Any]) -> dict[str, Any]:
        has_username = "username" in values
        has_password = "password" in values
        if has_username != has_password:
            raise ValueError("Both 'username' and 'password' needs to be set")
        return values

    @model_validator(mode="before")
    @classmethod
    def set_transport(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("transport") == RequesterTransport.JSON:
            playback = JSONPlayback()
            if "requester" not in values:
                values["requester"] = playback.async_request
            if "sync_requester" not in values:
                values["sync_requester"] = playback.sync_request

        return values

    @model_validator(mode="before")
    @classmethod
    def validate_mix_authentication_schemes(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("password") and values.get("api_token"):
            raise ValueError("Unable to combine password with token based authentication")
        return values

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        if is_valid_url(value):
            return value.rstrip("/")

        raise ValueError("The configured address is not a valid url")

    @model_validator(mode="after")
    def validate_proxy_config(self) -> Self:
        if self.proxy and self.proxy_mounts.is_set:  # pylint: disable=no-member
            raise ValueError("'proxy' and 'proxy_mounts' are mutually exclusive")
        return self

    @property
    def default_infrahub_branch(self) -> str:
        branch: Optional[str] = None
        if not self.default_branch_from_git:
            branch = self.default_branch

        return get_branch(branch=branch)

    @property
    def password_authentication(self) -> bool:
        return bool(self.username)


class Config(ConfigBase):
    recorder: RecorderType = Field(default=RecorderType.NONE, description="Select builtin recorder for later replay.")
    custom_recorder: Recorder = Field(
        default_factory=NoRecorder.default, description="Provides a way to record responses from the Infrahub API"
    )
    requester: Optional[AsyncRequester] = None
    sync_requester: Optional[SyncRequester] = None
    log: Optional[Any] = None

    @property
    def logger(self) -> InfrahubLoggers:
        # We expect the log to adhere to the definitions defined by the InfrahubLoggers object
        # When using structlog the logger doesn't expose the expected methods by looking at the
        # object to pydantic rejects them. This is a workaround to allow structlog to be used
        # as a logger
        return self.log  # type: ignore

    @model_validator(mode="before")
    @classmethod
    def set_custom_recorder(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("recorder") == RecorderType.NONE and "custom_recorder" not in values:
            values["custom_recorder"] = NoRecorder()
        elif values.get("recorder") == RecorderType.JSON and "custom_recorder" not in values:
            values["custom_recorder"] = JSONRecorder()
        return values
