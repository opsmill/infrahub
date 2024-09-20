from __future__ import annotations

import os
import os.path
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import toml
from infrahub_sdk import generate_uuid
from pydantic import AliasChoices, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

from infrahub.database.constants import DatabaseType
from infrahub.exceptions import InitializationError

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


class CacheDriver(str, Enum):
    Redis = "redis"
    NATS = "nats"


class WorkflowDriver(str, Enum):
    LOCAL = "local"
    WORKER = "worker"


class MainSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_")
    docs_index_path: str = Field(
        default="/opt/infrahub/docs/build/search-index.json",
        description="Full path of saved json containing pre-indexed documentation",
    )
    internal_address: Optional[str] = Field(default=None)
    allow_anonymous_access: bool = Field(
        default=True, description="Indicates if the system allows anonymous read access"
    )
    telemetry_optout: bool = Field(default=False, description="Disable anonymous usage reporting")
    telemetry_endpoint: str = "https://telemetry.opsmill.cloud/infrahub"
    telemetry_interval: int = Field(
        default=3600 * 24, ge=60, description="Time (in seconds) between telemetry usage push"
    )
    permission_backends: list[str] = Field(
        default=["infrahub.permissions.LocalPermissionBackend"],
        description="List of modules to handle permissions, they will be run in the given order",
    )


class FileSystemStorageSettings(BaseSettings):
    # Make variable lookup case-sensitive to avoid fetching $PATH value
    model_config = SettingsConfigDict(case_sensitive=True)
    path_: str = Field(
        default="/opt/infrahub/storage",
        alias="path",
        validation_alias=AliasChoices("INFRAHUB_STORAGE_LOCAL_PATH", "infrahub_storage_local_path", "path"),
    )


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
        default="",
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
    database: Optional[str] = Field(default=None, pattern=VALID_DATABASE_NAME_REGEX, description="Name of the database")
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    tls_insecure: bool = Field(default=False, description="Indicates if TLS certificates are verified")
    tls_ca_file: Optional[str] = Field(default=None, description="File path to CA cert or bundle in PEM format")
    query_size_limit: int = Field(
        default=5000,
        ge=1,
        le=20000,
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

    @property
    def database_name(self) -> str:
        return self.database or self.db_type.value


class BrokerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_BROKER_")
    enable: bool = True
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    tls_insecure: bool = Field(default=False, description="Indicates if TLS certificates are verified")
    tls_ca_file: Optional[str] = Field(default=None, description="File path to CA cert or bundle in PEM format")
    username: str = "infrahub"
    password: str = "infrahub"
    address: str = "localhost"
    port: Optional[int] = Field(default=None, ge=1, le=65535, description="Specified if running on a non default port.")
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
    port: Optional[int] = Field(
        default=None, ge=1, le=65535, description="Specified if running on a non default port (6379)"
    )
    database: int = Field(default=0, ge=0, le=15, description="Id of the database to use")
    driver: CacheDriver = CacheDriver.Redis
    username: str = "infrahub"
    password: str = "infrahub"
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    tls_insecure: bool = Field(default=False, description="Indicates if TLS certificates are verified")
    tls_ca_file: Optional[str] = Field(default=None, description="File path to CA cert or bundle in PEM format")

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
    port: Optional[int] = Field(default=None, ge=1, le=65535, description="Specified if running on a non default port.")
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    driver: WorkflowDriver = WorkflowDriver.WORKER

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
        default=10, ge=0, description="Time (in seconds) between git repositories synchronizations"
    )


class InitialSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_INITIAL_")
    default_branch: str = Field(
        default="main",
        description="Defines the name of the default branch within Infrahub, can only be set once during initialization of the system.",
    )
    admin_token: Optional[str] = Field(default=None, description="An optional initial token for the admin account.")
    admin_password: str = Field(default="infrahub", description="The initial password for the admin user")
    agent_token: Optional[str] = Field(default=None, description="An optional initial token for a git-agent account.")
    agent_password: Optional[str] = Field(
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
    frontend_dsn: Optional[str] = None
    api_server_dsn: Optional[str] = None
    git_agent_dsn: Optional[str] = None


class LoggingSettings(BaseSettings):
    remote: RemoteLoggingSettings = RemoteLoggingSettings()


class AnalyticsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_ANALYTICS_")
    enable: bool = True
    address: Optional[str] = None
    api_key: Optional[str] = None


class ExperimentalFeaturesSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_EXPERIMENTAL_")
    pull_request: bool = False
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
    exporter_endpoint: Optional[str] = Field(default=None, description="OTLP endpoint for exporting traces")


@dataclass
class Override:
    message_bus: Optional[InfrahubMessageBus] = None
    cache: Optional[InfrahubCache] = None
    workflow: Optional[InfrahubWorkflow] = None


@dataclass
class ConfiguredSettings:
    settings: Optional[Settings] = None

    def initialize(self, config_file: Optional[str] = None) -> None:
        """Initialize the settings if they have not been initialized."""
        if self.initialized:
            return
        if not config_file:
            config_file_name = os.environ.get("INFRAHUB_CONFIG", "infrahub.toml")
            config_file = os.path.abspath(config_file_name)
        load(config_file)

    def initialize_and_exit(self, config_file: Optional[str] = None) -> None:
        """Initialize the settings if they have not been initialized, exit on failures."""
        if self.initialized:
            return
        if not config_file:
            config_file_name = os.environ.get("INFRAHUB_CONFIG", "infrahub.toml")
            config_file = os.path.abspath(config_file_name)
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
    def database(self) -> DatabaseSettings:
        return self.active_settings.database

    @property
    def broker(self) -> BrokerSettings:
        return self.active_settings.broker

    @property
    def cache(self) -> CacheSettings:
        return self.active_settings.cache

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


def load(config_file_name: str = "infrahub.toml", config_data: Optional[dict[str, Any]] = None) -> None:
    """Load configuration.

    Configuration is loaded from a config file in toml format that contains the settings,
    or from a dictionary of those settings passed in as "config_data"
    """

    if config_data:
        SETTINGS.settings = Settings(**config_data)
        return

    if os.path.exists(config_file_name):
        config_string = Path(config_file_name).read_text(encoding="utf-8")
        config_tmp = toml.loads(config_string)

        SETTINGS.settings = Settings(**config_tmp)
        return

    SETTINGS.settings = Settings()


def load_and_exit(config_file_name: str = "infrahub.toml", config_data: Optional[dict[str, Any]] = None) -> None:
    """Calls load, but wraps it in a try except block.

    This is done to handle a ValidationError which is raised when settings are specified but invalid.
    In such cases, a message is printed to the screen indicating the settings which don't pass validation.

    Args:
        config_file_name (str, optional): [description]. Defaults to "pyproject.toml".
        config_data (dict, optional): [description]. Defaults to None.
    """
    try:
        load(config_file_name=config_file_name, config_data=config_data)
    except ValidationError as err:
        print(f"Configuration not valid, found {len(err.errors())} error(s)")
        for error in err.errors():
            error_locations = [str(location) for location in error["loc"]]
            print(f"  {'/'.join(error_locations)} | {error['msg']} ({error['type']})")
        sys.exit(1)


OVERRIDE: Override = Override()
SETTINGS: ConfiguredSettings = ConfiguredSettings()
