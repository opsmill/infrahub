from __future__ import annotations

import os
import ssl
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import toml
from infrahub_sdk.utils import generate_uuid
from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    PrivateAttr,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

from infrahub.database.constants import DatabaseType
from infrahub.exceptions import InitializationError, ProcessingError

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.adapters.message_bus import InfrahubMessageBus
    from infrahub.services.adapters.workflow import InfrahubWorkflow


VALID_DATABASE_NAME_REGEX = r"^[a-z][a-z0-9\.]+$"
THIRTY_DAYS_IN_SECONDS = 3600 * 24 * 30


def default_cors_allow_methods() -> list[str]:
    return ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]


def default_cors_allow_headers() -> list[str]:
    return ["accept", "authorization", "content-type", "user-agent", "x-csrftoken", "x-requested-with"]


def default_append_git_suffix_domains() -> list[str]:
    return ["github.com", "gitlab.com"]


class UserInfoMethod(str, Enum):
    POST = "post"
    GET = "get"


class SSOProtocol(str, Enum):
    OAUTH2 = "oauth2"
    OIDC = "oidc"


class Oauth2Provider(str, Enum):
    GOOGLE = "google"
    PROVIDER1 = "provider1"
    PROVIDER2 = "provider2"


class OIDCProvider(str, Enum):
    GOOGLE = "google"
    PROVIDER1 = "provider1"
    PROVIDER2 = "provider2"


class SSOInfo(BaseModel):
    providers: list[SSOProviderInfo] = Field(default_factory=list)

    @computed_field
    def enabled(self) -> bool:
        return bool(self.providers)


class SSOProviderInfo(BaseModel):
    name: str
    display_label: str
    icon: str
    protocol: SSOProtocol

    @computed_field
    def authorize_path(self) -> str:
        return f"/api/{self.protocol.value}/{self.name}/authorize"

    @computed_field
    def token_path(self) -> str:
        return f"/api/{self.protocol.value}/{self.name}/token"


class StorageDriver(str, Enum):
    FileSystemStorage = "local"
    InfrahubS3ObjectStorage = "s3"


class TraceExporterType(str, Enum):
    CONSOLE = "console"
    OTLP = "otlp"
    # JAEGER = "jaeger"
    # ZIPKIN = "zipkin"


class TraceTransportProtocol(str, Enum):
    GRPC = "grpc"
    HTTP_PROTOBUF = "http/protobuf"
    # HTTP_JSON = "http/json"


class BrokerDriver(str, Enum):
    RabbitMQ = "rabbitmq"
    NATS = "nats"

    @property
    def driver_module_path(self) -> str:
        match self:
            case BrokerDriver.NATS:
                return "infrahub.services.adapters.message_bus.nats"
            case BrokerDriver.RabbitMQ:
                return "infrahub.services.adapters.message_bus.rabbitmq"

    @property
    def driver_class_name(self) -> str:
        match self:
            case BrokerDriver.NATS:
                return "NATSMessageBus"
            case BrokerDriver.RabbitMQ:
                return "RabbitMQMessageBus"


class CacheDriver(str, Enum):
    Redis = "redis"
    NATS = "nats"

    @property
    def driver_module_path(self) -> str:
        match self:
            case CacheDriver.NATS:
                return "infrahub.services.adapters.cache.nats"
            case CacheDriver.Redis:
                return "infrahub.services.adapters.cache.redis"

    @property
    def driver_class_name(self) -> str:
        match self:
            case CacheDriver.NATS:
                return "NATSCache"
            case CacheDriver.Redis:
                return "RedisCache"


class WorkflowDriver(str, Enum):
    LOCAL = "local"
    WORKER = "worker"


class ExtraLogLevel(str, Enum):
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class MainSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_")
    docs_index_path: Path = Field(
        default=Path("/opt/infrahub/docs/build/search-index.json"),
        description="Full path of saved json containing pre-indexed documentation",
    )
    internal_address: str | None = Field(default=None)
    allow_anonymous_access: bool = Field(
        default=True, description="Indicates if the system allows anonymous read access"
    )
    anonymous_access_role: str = Field(
        default="Anonymous User", description="Name of the role defining which permissions anonymous users have"
    )
    telemetry_optout: bool = Field(default=False, description="Disable anonymous usage reporting")
    telemetry_endpoint: str = "https://telemetry.opsmill.cloud/infrahub"
    permission_backends: list[str] = Field(
        default=["infrahub.permissions.LocalPermissionBackend"],
        description="List of modules to handle permissions, they will be run in the given order",
    )
    public_url: str | None = Field(
        default=None,
        description="Define the public URL of the Infrahub, might be required for OAuth2 and OIDC depending on your infrastructure.",
    )
    schema_strict_mode: bool = Field(
        default=True,
        description="Enable strict schema validation. When set to `False`, "
        "`human_friendly_id` schema fields should not necessarily target a unique combination of peer attributes.",
    )

    @field_validator("docs_index_path", mode="before")
    @classmethod
    def convert_to_path(cls, value: Path | str) -> Path:
        return Path(value) if isinstance(value, str) else value


class FileSystemStorageSettings(BaseSettings):
    # Make variable lookup case-sensitive to avoid fetching $PATH value
    model_config = SettingsConfigDict(case_sensitive=True)
    path_: Path = Field(
        default=Path("/opt/infrahub/storage"),
        alias="path",
        validation_alias=AliasChoices("INFRAHUB_STORAGE_LOCAL_PATH", "infrahub_storage_local_path", "path"),
    )

    @field_validator("path_", mode="before")
    @classmethod
    def convert_to_path(cls, value: Path | str) -> Path:
        return Path(value) if isinstance(value, str) else value


class S3StorageSettings(BaseSettings):
    access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID", validation_alias="AWS_ACCESS_KEY_ID")
    secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY", validation_alias="AWS_SECRET_ACCESS_KEY")
    bucket_name: str = Field(
        default="",
        alias="AWS_S3_BUCKET_NAME",
        validation_alias=AliasChoices("INFRAHUB_STORAGE_BUCKET_NAME", "AWS_S3_BUCKET_NAME"),
    )
    endpoint_url: str = Field(
        default="",
        alias="AWS_S3_ENDPOINT_URL",
        validation_alias=AliasChoices("INFRAHUB_STORAGE_ENDPOINT_URL", "AWS_S3_ENDPOINT_URL"),
    )
    use_ssl: bool = Field(
        default=True,
        alias="AWS_S3_USE_SSL",
        validation_alias=AliasChoices("INFRAHUB_STORAGE_USE_SSL", "AWS_S3_USE_SSL"),
    )
    default_acl: str = Field(
        default="private",
        alias="AWS_DEFAULT_ACL",
        validation_alias=AliasChoices("INFRAHUB_STORAGE_DEFAULT_ACL", "AWS_DEFAULT_ACL"),
    )
    querystring_auth: bool = Field(
        default=False,
        alias="AWS_QUERYSTRING_AUTH",
        validation_alias=AliasChoices("INFRAHUB_STORAGE_QUERYSTRING_AUTH", "AWS_QUERYSTRING_AUTH"),
    )
    custom_domain: str = Field(
        default="",
        alias="AWS_S3_CUSTOM_DOMAIN",
        validation_alias=AliasChoices("INFRAHUB_STORAGE_CUSTOM_DOMAIN", "AWS_S3_CUSTOM_DOMAIN"),
    )


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_STORAGE_")
    driver: StorageDriver = StorageDriver.FileSystemStorage
    local: FileSystemStorageSettings = FileSystemStorageSettings()
    s3: S3StorageSettings = S3StorageSettings()


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_DB_")
    db_type: DatabaseType = Field(
        default=DatabaseType.NEO4J, validation_alias=AliasChoices("INFRAHUB_DB_TYPE", "db_type")
    )
    protocol: str = "bolt"
    username: str = "neo4j"
    password: str = "admin"
    address: str = "localhost"
    port: int = 7687
    database: str | None = Field(default=None, pattern=VALID_DATABASE_NAME_REGEX, description="Name of the database")
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    tls_insecure: bool = Field(default=False, description="Indicates if TLS certificates are verified")
    tls_ca_file: str | None = Field(default=None, description="File path to CA cert or bundle in PEM format")
    query_size_limit: int = Field(
        default=5_000,
        ge=1,
        le=20_000,
        description="The max number of records to fetch in a single query before performing internal pagination.",
    )
    max_depth_search_hierarchy: int = Field(
        default=5,
        le=20,
        description="Maximum number of level to search in a hierarchy.",
    )
    retry_limit: int = Field(
        default=3, description="Maximum number of times a transient issue in a transaction should be retried."
    )
    max_concurrent_queries: int = Field(
        default=0, ge=0, description="Maximum number of concurrent queries that can run (0 means unlimited)."
    )
    max_concurrent_queries_delay: float = Field(
        default=0.01, ge=0, description="Delay to add when max_concurrent_queries is reached."
    )

    @property
    def database_name(self) -> str:
        return self.database or self.db_type.value


class DevelopmentSettings(BaseSettings):
    """The development settings are only relevant for local development"""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_DEV_")

    frontend_redirect_sso: bool = Field(
        default=False,
        description="Indicates of the frontend should be responsible for the SSO redirection",
    )


class BrokerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_BROKER_")
    enable: bool = True
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    tls_insecure: bool = Field(default=False, description="Indicates if TLS certificates are verified")
    tls_ca_file: str | None = Field(default=None, description="File path to CA cert or bundle in PEM format")
    username: str = "infrahub"
    password: str = "infrahub"
    address: str = "localhost"
    port: int | None = Field(default=None, ge=1, le=65535, description="Specified if running on a non default port.")
    rabbitmq_http_port: int | None = Field(default=None, ge=1, le=65535)
    namespace: str = "infrahub"
    maximum_message_retries: int = Field(
        default=10, description="The maximum number of retries that are attempted for failed messages"
    )
    maximum_concurrent_messages: int = Field(
        default=2, description="The maximum number of concurrent messages fetched by each worker", ge=1
    )
    virtualhost: str = Field(default="/", description="The virtual host to connect to")
    driver: BrokerDriver = BrokerDriver.RabbitMQ

    @property
    def service_port(self) -> int:
        default_ports: dict[bool, int] = {True: 5671, False: 5672}
        if self.driver == BrokerDriver.NATS:
            return self.port or 4222
        return self.port or default_ports[self.tls_enabled]


class CacheSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_CACHE_")
    enable: bool = True
    address: str = "localhost"
    port: int | None = Field(
        default=None, ge=1, le=65535, description="Specified if running on a non default port (6379)"
    )
    database: int = Field(default=0, ge=0, le=15, description="Id of the database to use")
    driver: CacheDriver = CacheDriver.Redis
    username: str = ""
    password: str = ""
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    tls_insecure: bool = Field(default=False, description="Indicates if TLS certificates are verified")
    tls_ca_file: str | None = Field(default=None, description="File path to CA cert or bundle in PEM format")

    @property
    def service_port(self) -> int:
        default_ports: int = 6379
        if self.driver == CacheDriver.NATS:
            return self.port or 4222
        return self.port or default_ports


class WorkflowSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_WORKFLOW_")
    enable: bool = True
    address: str = "localhost"
    port: int | None = Field(default=None, ge=1, le=65535, description="Specified if running on a non default port.")
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    driver: WorkflowDriver = WorkflowDriver.WORKER
    default_worker_type: str = "infrahubasync"
    extra_loggers: list[str] = Field(
        default_factory=list, description="A list of additional logger that will be captured during task execution."
    )
    extra_log_level: ExtraLogLevel = Field(
        default=ExtraLogLevel.INFO, description="Log level applied to all extra loggers."
    )
    worker_polling_interval: int = Field(
        default=2, ge=1, le=30, description="Specify how often the worker should poll the server for tasks (sec)"
    )

    @property
    def api_endpoint(self) -> str:
        url = "https://" if self.tls_enabled else "http://"
        url += self.address
        if self.port:
            url += f":{self.port}"
        url += "/api"
        return url


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_API_")
    cors_allow_origins: list[str] = Field(
        default_factory=list, description="A list of origins that are authorized to make cross-site HTTP requests"
    )
    cors_allow_methods: list[str] = Field(
        default_factory=default_cors_allow_methods,
        description="A list of HTTP verbs that are allowed for the actual request",
    )
    cors_allow_headers: list[str] = Field(
        default_factory=default_cors_allow_headers,
        description="The list of non-standard HTTP headers allowed in requests from the browser",
    )
    cors_allow_credentials: bool = Field(
        default=True, description="If True, cookies will be allowed to be included in cross-site HTTP requests"
    )


class GitSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_GIT_")
    repositories_directory: str = "repositories"
    sync_interval: int = Field(
        default=10,
        ge=0,
        description="Time (in seconds) between git repositories synchronizations",
        deprecated="This setting is deprecated and not currently in use.",
    )
    append_git_suffix: list[str] = Field(
        default_factory=default_append_git_suffix_domains,
        description="Automatically append '.git' to HTTP URLs if for these domains.",
    )


class HTTPSettings(BaseSettings):
    """The HTTP settings control how Infrahub interacts with external HTTP servers

    This can be things like webhooks and OAuth2 providers"""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_HTTP_")
    timeout: int = Field(default=10, description="Default connection timeout in seconds")
    tls_insecure: bool = Field(
        default=False,
        description="Indicates if Infrahub will validate server certificates or if the validation is ignored.",
    )
    tls_ca_bundle: str | None = Field(
        default=None,
        description="Custom CA bundle in PEM format. The value should either be the CA bundle as a string, alternatively as a file path.",
    )

    @model_validator(mode="after")
    def set_tls_context(self) -> Self:
        try:
            # Validate that the context can be created, we want to raise this error during application start
            # instead of running into issues later when we first try to use the tls context.
            self.get_tls_context()
        except ssl.SSLError as exc:
            raise ValueError(f"Unable load CA bundle from {self.tls_ca_bundle}: {exc}") from exc

        return self

    def get_tls_context(self) -> ssl.SSLContext:
        if self.tls_insecure:
            return ssl._create_unverified_context()

        if not self.tls_ca_bundle:
            return ssl.create_default_context()

        tls_ca_path = Path(self.tls_ca_bundle)

        try:
            possibly_file = tls_ca_path.exists()
        except OSError:
            # Raised if the filename is too long which can indicate
            # that the value is a PEM certificate in string form.
            possibly_file = False

        if possibly_file and tls_ca_path.is_file():
            context = ssl.create_default_context(cafile=str(tls_ca_path))
        else:
            context = ssl.create_default_context()
            context.load_verify_locations(cadata=self.tls_ca_bundle)

        return context


class InitialSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_INITIAL_")
    default_branch: str = Field(
        default="main",
        description="Defines the name of the default branch within Infrahub, can only be set once during initialization of the system.",
    )
    admin_token: str | None = Field(default=None, description="An optional initial token for the admin account.")
    admin_password: str = Field(default="infrahub", description="The initial password for the admin user")
    agent_token: str | None = Field(default=None, description="An optional initial token for a git-agent account.")
    agent_password: str | None = Field(
        default=None, description="An optional initial password for a git-agent account."
    )

    @property
    def create_agent_user(self) -> bool:
        if self.agent_token or self.agent_password:
            return True
        return False

    @model_validator(mode="after")
    def check_tokens_match(self) -> Self:
        if self.admin_token is not None and self.agent_token is not None and self.admin_token == self.agent_token:
            raise ValueError("Initial user tokens can't have the same values")
        return self


def _default_scopes() -> list[str]:
    return ["openid", "profile", "email"]


class SecurityOIDCBaseSettings(BaseSettings):
    """Baseclass for typing"""

    icon: str = Field(default="mdi:account-key")
    display_label: str = Field(default="Single Sign on")
    userinfo_method: UserInfoMethod = Field(default=UserInfoMethod.GET)


class SecurityOIDCSettings(SecurityOIDCBaseSettings):
    client_id: str = Field(..., description="Client ID of the application created in the auth provider")
    client_secret: str = Field(..., description="Client secret as defined in auth provider")
    discovery_url: str = Field(..., description="The OIDC discovery URL xyz/.well-known/openid-configuration")
    scopes: list[str] = Field(default_factory=_default_scopes)


class SecurityOIDCGoogle(SecurityOIDCSettings):
    """Settings for the custom OIDC provider"""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OIDC_GOOGLE_")

    discovery_url: str = Field(default="https://accounts.google.com/.well-known/openid-configuration")
    icon: str = Field(default="mdi:google")
    display_label: str = Field(default="Google")


class SecurityOIDCProvider1(SecurityOIDCSettings):
    """Settings for the custom OIDC provider"""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OIDC_PROVIDER1_")


class SecurityOIDCProvider2(SecurityOIDCSettings):
    """Settings for the custom OIDC provider"""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OIDC_PROVIDER2_")


class SecurityOIDCProviderSettings(BaseModel):
    """This class is meant to facilitate configuration of OIDC providers when loading configuration from a infrahub.toml file."""

    google: SecurityOIDCGoogle | None = Field(default=None)
    provider1: SecurityOIDCProvider1 | None = Field(default=None)
    provider2: SecurityOIDCProvider2 | None = Field(default=None)


class SecurityOAuth2BaseSettings(BaseSettings):
    """Baseclass for typing"""

    icon: str = Field(default="mdi:account-key")
    userinfo_method: UserInfoMethod = Field(default=UserInfoMethod.GET)


class SecurityOAuth2Settings(SecurityOAuth2BaseSettings):
    """Common base for Oauth2 providers"""

    client_id: str = Field(..., description="Client ID of the application created in the auth provider")
    client_secret: str = Field(..., description="Client secret as defined in auth provider")
    authorization_url: str = Field(...)
    token_url: str = Field(...)
    userinfo_url: str = Field(...)
    scopes: list[str] = Field(default_factory=_default_scopes)
    display_label: str = Field(default="Single Sign on")


class SecurityOAuth2Provider1(SecurityOAuth2Settings):
    """Common base for Oauth2 providers"""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OAUTH2_PROVIDER1_")


class SecurityOAuth2Provider2(SecurityOAuth2Settings):
    """Common base for Oauth2 providers"""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OAUTH2_PROVIDER2_")


class SecurityOAuth2Google(SecurityOAuth2Settings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OAUTH2_GOOGLE_")
    authorization_url: str = Field(default="https://accounts.google.com/o/oauth2/auth")
    token_url: str = Field(default="https://oauth2.googleapis.com/token")
    userinfo_url: str = Field(default="https://www.googleapis.com/oauth2/v3/userinfo")
    icon: str = Field(default="mdi:google")
    display_label: str = Field(default="Google")


class SecurityOAuth2ProviderSettings(BaseModel):
    """This class is meant to facilitate configuration of OAuth2 providers when loading configuration from a infrahub.toml file."""

    google: SecurityOAuth2Google | None = Field(default=None)
    provider1: SecurityOAuth2Provider1 | None = Field(default=None)
    provider2: SecurityOAuth2Provider2 | None = Field(default=None)


class MiscellaneousSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_MISC_")
    print_query_details: bool = False
    start_background_runner: bool = True
    maximum_validator_execution_time: int = Field(
        default=1800, description="The maximum allowed time (in seconds) for a validator to run."
    )
    response_delay: int = Field(default=0, description="Arbitrary delay to add when processing API requests.")


class RemoteLoggingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_LOGGING_REMOTE_")
    enable: bool = False
    frontend_dsn: str | None = None
    api_server_dsn: str | None = None
    git_agent_dsn: str | None = None


class LoggingSettings(BaseSettings):
    remote: RemoteLoggingSettings = RemoteLoggingSettings()


class AnalyticsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_ANALYTICS_")
    enable: bool = True
    address: str | None = None
    api_key: str | None = None


class ExperimentalFeaturesSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_EXPERIMENTAL_")
    graphql_enums: bool = False


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_SECURITY_")
    access_token_lifetime: int = Field(default=3600, description="Lifetime of access token in seconds")
    refresh_token_lifetime: int = Field(
        default=THIRTY_DAYS_IN_SECONDS, description="Lifetime of refresh token in seconds"
    )
    secret_key: str = Field(
        default_factory=generate_uuid, description="The secret key used to validate authentication tokens"
    )
    oauth2_providers: list[Oauth2Provider] = Field(default_factory=list, description="The selected OAuth2 providers")
    oauth2_provider_settings: SecurityOAuth2ProviderSettings = Field(default_factory=SecurityOAuth2ProviderSettings)
    oidc_providers: list[OIDCProvider] = Field(default_factory=list, description="The selected OIDC providers")
    oidc_provider_settings: SecurityOIDCProviderSettings = Field(default_factory=SecurityOIDCProviderSettings)
    restrict_untrusted_jinja2_filters: bool = Field(
        default=True, description="Indicates if untrusted Jinja2 filters should be disallowd for computed attributes"
    )
    _oauth2_settings: dict[str, SecurityOAuth2Settings] = PrivateAttr(default_factory=dict)
    _oidc_settings: dict[str, SecurityOIDCSettings] = PrivateAttr(default_factory=dict)
    sso_user_default_group: str | None = Field(
        default=None,
        description="Name of the group to which users authenticated via SSO will belong if not provided by identity provider",
    )

    @model_validator(mode="after")
    def check_oauth2_provider_settings(self) -> Self:
        mapped_providers: dict[Oauth2Provider, type[SecurityOAuth2BaseSettings]] = {
            Oauth2Provider.PROVIDER1: SecurityOAuth2Provider1,
            Oauth2Provider.PROVIDER2: SecurityOAuth2Provider2,
            Oauth2Provider.GOOGLE: SecurityOAuth2Google,
        }
        for oauth2_provider in self.oauth2_providers:
            match oauth2_provider:
                case Oauth2Provider.GOOGLE:
                    if self.oauth2_provider_settings.google:
                        self._oauth2_settings[oauth2_provider.value] = self.oauth2_provider_settings.google
                case Oauth2Provider.PROVIDER1:
                    if self.oauth2_provider_settings.provider1:
                        self._oauth2_settings[oauth2_provider.value] = self.oauth2_provider_settings.provider1
                case Oauth2Provider.PROVIDER2:
                    if self.oauth2_provider_settings.provider2:
                        self._oauth2_settings[oauth2_provider.value] = self.oauth2_provider_settings.provider2

            if oauth2_provider.value not in self._oauth2_settings:
                provider = mapped_providers[oauth2_provider]()
                if isinstance(provider, SecurityOAuth2Settings):
                    self._oauth2_settings[oauth2_provider.value] = provider

        return self

    @model_validator(mode="after")
    def check_oidc_provider_settings(self) -> Self:
        mapped_providers: dict[OIDCProvider, type[SecurityOIDCBaseSettings]] = {
            OIDCProvider.GOOGLE: SecurityOIDCGoogle,
            OIDCProvider.PROVIDER1: SecurityOIDCProvider1,
            OIDCProvider.PROVIDER2: SecurityOIDCProvider2,
        }
        for oidc_provider in self.oidc_providers:
            match oidc_provider:
                case OIDCProvider.GOOGLE:
                    if self.oidc_provider_settings.google:
                        self._oidc_settings[oidc_provider.value] = self.oidc_provider_settings.google
                case OIDCProvider.PROVIDER1:
                    if self.oidc_provider_settings.provider1:
                        self._oidc_settings[oidc_provider.value] = self.oidc_provider_settings.provider1
                case OIDCProvider.PROVIDER2:
                    if self.oidc_provider_settings.provider2:
                        self._oidc_settings[oidc_provider.value] = self.oidc_provider_settings.provider2

            if oidc_provider.value not in self._oidc_settings:
                provider = mapped_providers[oidc_provider]()
                if isinstance(provider, SecurityOIDCSettings):
                    self._oidc_settings[oidc_provider.value] = provider

        return self

    def get_oauth2_provider(self, provider: str) -> SecurityOAuth2Settings:
        if provider in self._oauth2_settings:
            return self._oauth2_settings[provider]

        raise ProcessingError(message=f"The provider {provider} has not been initialized")

    def get_oidc_provider(self, provider: str) -> SecurityOIDCSettings:
        if provider in self._oidc_settings:
            return self._oidc_settings[provider]

        raise ProcessingError(message=f"The provider {provider} has not been initialized")

    @property
    def public_sso_config(self) -> SSOInfo:
        oauth2_providers = [
            SSOProviderInfo(
                name=provider,
                display_label=self._oauth2_settings[provider].display_label,
                icon=self._oauth2_settings[provider].icon,
                protocol=SSOProtocol.OAUTH2,
            )
            for provider in self._oauth2_settings
        ]
        oidc_providers = [
            SSOProviderInfo(
                name=provider,
                display_label=self._oidc_settings[provider].display_label,
                icon=self._oidc_settings[provider].icon,
                protocol=SSOProtocol.OIDC,
            )
            for provider in self._oidc_settings
        ]
        return SSOInfo(providers=oauth2_providers + oidc_providers)


class TraceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_TRACE_")
    enable: bool = Field(default=False)
    insecure: bool = Field(
        default=True, description="Use insecure connection (HTTP) if True, otherwise use secure connection (HTTPS)"
    )
    exporter_type: TraceExporterType = Field(
        default=TraceExporterType.CONSOLE, description="Type of exporter to be used for tracing"
    )
    exporter_protocol: TraceTransportProtocol = Field(
        default=TraceTransportProtocol.GRPC, description="Protocol to be used for exporting traces"
    )
    exporter_endpoint: str | None = Field(default=None, description="OTLP endpoint for exporting traces")


@dataclass
class Override:
    message_bus: InfrahubMessageBus | None = None
    cache: InfrahubCache | None = None
    workflow: InfrahubWorkflow | None = None


@dataclass
class ConfiguredSettings:
    settings: Settings | None = None

    def initialize(self, config_file: Path | str | None = None) -> None:
        """Initialize the settings if they have not been initialized."""
        if self.initialized:
            return
        if not config_file:
            config_file_name: str = os.environ.get("INFRAHUB_CONFIG", "infrahub.toml")
            config_file = Path(config_file_name).resolve()
        self.settings = load(config_file)

    def initialize_and_exit(self, config_file: Path | str | None = None) -> None:
        """Initialize the settings if they have not been initialized, exit on failures."""
        if self.initialized:
            return
        if not config_file:
            config_file_name = os.environ.get("INFRAHUB_CONFIG", "infrahub.toml")
            config_file = Path(config_file_name).resolve()
        load_and_exit(config_file)

    @property
    def active_settings(self) -> Settings:
        if self.settings:
            return self.settings
        raise InitializationError

    @property
    def initialized(self) -> bool:
        return self.settings is not None

    @property
    def main(self) -> MainSettings:
        return self.active_settings.main

    @property
    def api(self) -> ApiSettings:
        return self.active_settings.api

    @property
    def git(self) -> GitSettings:
        return self.active_settings.git

    @property
    def http(self) -> HTTPSettings:
        return self.active_settings.http

    @property
    def database(self) -> DatabaseSettings:
        return self.active_settings.database

    @property
    def broker(self) -> BrokerSettings:
        return self.active_settings.broker

    @property
    def cache(self) -> CacheSettings:
        return self.active_settings.cache

    @property
    def dev(self) -> DevelopmentSettings:
        return self.active_settings.dev

    @property
    def workflow(self) -> WorkflowSettings:
        return self.active_settings.workflow

    @property
    def miscellaneous(self) -> MiscellaneousSettings:
        return self.active_settings.miscellaneous

    @property
    def initial(self) -> InitialSettings:
        return self.active_settings.initial

    @property
    def logging(self) -> LoggingSettings:
        return self.active_settings.logging

    @property
    def analytics(self) -> AnalyticsSettings:
        return self.active_settings.analytics

    @property
    def security(self) -> SecuritySettings:
        return self.active_settings.security

    @property
    def storage(self) -> StorageSettings:
        return self.active_settings.storage

    @property
    def trace(self) -> TraceSettings:
        return self.active_settings.trace

    @property
    def experimental_features(self) -> ExperimentalFeaturesSettings:
        return self.active_settings.experimental_features


class Settings(BaseSettings):
    """Main Settings Class for the project."""

    main: MainSettings = MainSettings()
    api: ApiSettings = ApiSettings()
    git: GitSettings = GitSettings()
    dev: DevelopmentSettings = DevelopmentSettings()
    http: HTTPSettings = HTTPSettings()
    database: DatabaseSettings = DatabaseSettings()
    broker: BrokerSettings = BrokerSettings()
    cache: CacheSettings = CacheSettings()
    workflow: WorkflowSettings = WorkflowSettings()
    miscellaneous: MiscellaneousSettings = MiscellaneousSettings()
    logging: LoggingSettings = LoggingSettings()
    analytics: AnalyticsSettings = AnalyticsSettings()
    initial: InitialSettings = InitialSettings()
    security: SecuritySettings = SecuritySettings()
    storage: StorageSettings = StorageSettings()
    trace: TraceSettings = TraceSettings()
    experimental_features: ExperimentalFeaturesSettings = ExperimentalFeaturesSettings()


def load(config_file_name: Path | str = "infrahub.toml", config_data: dict[str, Any] | None = None) -> Settings:
    """Load configuration.

    Configuration is loaded from a config file in toml format that contains the settings,
    or from a dictionary of those settings passed in as "config_data"
    """
    config_file = Path(config_file_name)

    if config_data:
        return Settings(**config_data)

    if config_file.exists():
        config_string = config_file.read_text(encoding="utf-8")
        config_tmp = toml.loads(config_string)

        return Settings(**config_tmp)

    return Settings()


def load_and_exit(config_file_name: Path | str = "infrahub.toml", config_data: dict[str, Any] | None = None) -> None:
    """Calls load, but wraps it in a try except block.

    This is done to handle a ValidationError which is raised when settings are specified but invalid.
    In such cases, a message is printed to the screen indicating the settings which don't pass validation.

    Args:
        config_file_name (str, optional): [description]. Defaults to "pyproject.toml".
        config_data (dict, optional): [description]. Defaults to None.
    """
    try:
        SETTINGS.settings = load(config_file_name=config_file_name, config_data=config_data)
    except ValidationError as err:
        print(f"Configuration not valid, found {len(err.errors())} error(s)")
        for error in err.errors():
            error_locations = [str(location) for location in error["loc"]]
            print(f"  {'/'.join(error_locations)} | {error['msg']} ({error['type']})")
        sys.exit(1)


OVERRIDE: Override = Override()
SETTINGS: ConfiguredSettings = ConfiguredSettings()
