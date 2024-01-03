from __future__ import annotations

import os
import os.path
import sys
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import toml
from infrahub_sdk import generate_uuid
from pydantic import AliasChoices, BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.adapters.message_bus import InfrahubMessageBus
else:
    # Avoid pydantic complaints
    # TODO: Is there a better way to fix this?
    InfrahubCache = InfrahubMessageBus = None

SETTINGS: Settings = None

VALID_DATABASE_NAME_REGEX = r"^[a-z][a-z0-9\.]+$"
THIRTY_DAYS_IN_SECONDS = 3600 * 24 * 30


class DatabaseType(str, Enum):
    NEO4J = "neo4j"
    MEMGRAPH = "memgraph"


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


class MainSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_")
    default_branch: str = "main"
    # default_account: str = "default"
    # default_account_perm: str = "CAN_READ"

    internal_address: str = "http://localhost:8000"
    allow_anonymous_access: bool = Field(
        default=True, description="Indicates if the system allows anonymous read access"
    )


class FileSystemStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_STORAGE_")
    path_: str = Field(
        default="/opt/infrahub/storage", alias="path", validation_alias=AliasChoices("path", "local_path")
    )


class S3StorageSettings(BaseSettings):
    access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID", validation_alias="AWS_ACCESS_KEY_ID")
    secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY", validation_alias="AWS_SECRET_ACCESS_KEY")
    bucket_name: str = Field(
        default="",
        alias="AWS_S3_BUCKET_NAME",
        validation_alias=AliasChoices("AWS_S3_BUCKET_NAME", "INFRAHUB_STORAGE_BUCKET_NAME"),
    )
    endpoint_url: str = Field(
        default="",
        alias="AWS_S3_ENDPOINT_URL",
        validation_alias=AliasChoices("AWS_S3_ENDPOINT_URL", "INFRAHUB_STORAGE_ENDPOINT_URL"),
    )
    use_ssl: bool = Field(
        default=True, alias="AWS_S3_US_SSL", validation_alias=AliasChoices("AWS_S3_US_SSL", "INFRAHUB_STORAGE_USE_SSL")
    )
    default_acl: str = Field(
        default="",
        alias="AWS_DEFAULT_ACL",
        validation_alias=AliasChoices("AWS_DEFAULT_ACL", "INFRAHUB_STORAGE_DEFAULT_ACL"),
    )
    querystring_auth: bool = Field(
        default=False,
        alias="AWS_QUERYSTRING_AUTH",
        validation_alias=AliasChoices("AWS_QUERYSTRING_AUTH", "INFRAHUB_STORAGE_QUERYTSTRING_AUTH"),
    )
    custom_domain: str = Field(
        default="",
        alias="AWS_S3_CUSTOM_DOMAIN",
        validation_alias=AliasChoices("AWS_S3_CUSTOM_DOMAIN", "INFRAHUB_STORAGE_CUSTOM_DOMAIN"),
    )


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_STORAGE")
    driver: StorageDriver = StorageDriver.FileSystemStorage
    local: FileSystemStorageSettings = FileSystemStorageSettings()
    s3: S3StorageSettings = S3StorageSettings()


class DatabaseSettings(BaseSettings):
    db_type: DatabaseType = Field(default=DatabaseType.MEMGRAPH, validation_alias="INFRAHUB_DB_TYPE")
    protocol: str = Field(default="bolt", validation_alias="NEO4J_PROTOCOL")
    username: str = Field(default="neo4j", validation_alias="NEO4J_USERNAME")
    password: str = Field(default="admin", validation_alias="NEO4J_PASSWORD")
    address: str = Field(default="localhost", validation_alias="NEO4J_ADDRESS")
    port: int = Field(default=7687, validation_alias="NEO4J_PORT")
    database: Optional[str] = Field(
        default=None,
        pattern=VALID_DATABASE_NAME_REGEX,
        description="Name of the database",
        validation_alias="NEO4J_DATABASE",
    )
    query_size_limit: int = Field(
        default=5000,
        ge=1,
        le=20000,
        description="The max number of records to fetch in a single query before performing internal pagination.",
        validation_alias="INFRAHUB_DB_QUERY_SIZE_LIMIT",
    )

    @property
    def database_name(self) -> str:
        return self.database or self.db_type.value


class BrokerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_BROKER_")
    enable: bool = True
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    username: str = "infrahub"
    password: str = "infrahub"
    address: str = "localhost"
    port: Optional[int] = Field(default=None, ge=1, le=65535, description="Specified if running on a non default port.")
    namespace: str = "infrahub"
    maximum_message_retries: int = Field(
        default=10, description="The maximum number of retries that are attempted for failed messages"
    )

    @property
    def service_port(self) -> int:
        default_ports: Dict[bool, int] = {True: 5671, False: 5672}
        return self.port or default_ports[self.tls_enabled]


class CacheSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_CACHE_")
    enable: bool = True
    address: str = "localhost"
    port: Optional[int] = Field(
        default=None, ge=1, le=65535, description="Specified if running on a non default port (6379)"
    )
    database: int = Field(default=0, ge=0, le=15, description="Id of the database to use")

    @property
    def service_port(self) -> int:
        default_ports: int = 6379
        return self.port or default_ports


class ApiSettings(BaseSettings):
    cors_allow_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]


class GitSettings(BaseSettings):
    repositories_directory: str = "repositories"


class MiscellaneousSettings(BaseSettings):
    print_query_details: bool = False
    start_background_runner: bool = True
    maximum_validator_execution_time: int = Field(
        default=1800, description="The maximum allowed time (in seconds) for a validator to run."
    )


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


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_SECURITY_")
    access_token_lifetime: int = Field(default=3600, description="Lifetime of access token in seconds")
    refresh_token_lifetime: int = Field(
        default=THIRTY_DAYS_IN_SECONDS, description="Lifetime of refresh token in seconds"
    )
    secret_key: str = Field(
        default_factory=generate_uuid, description="The secret key used to validate authentication tokens"
    )
    initial_admin_password: str = Field(default="infrahub", description="The initial password for the admin user")
    initial_admin_token: Optional[str] = Field(
        default=None, description="An optional initial token for the admin account."
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
    exporter_port: Optional[int] = Field(
        default=None, ge=1, le=65535, description="Specified if running on a non default port (4317)"
    )

    @property
    def service_port(self) -> int:
        if self.exporter_protocol == TraceTransportProtocol.GRPC:
            default_port = 4317
        elif self.exporter_protocol == TraceTransportProtocol.HTTP_PROTOBUF:
            default_port = 4318
        else:
            default_port = 4317

        return self.exporter_port or default_port

    @property
    def trace_endpoint(self) -> Optional[str]:
        if not self.exporter_endpoint:
            return None
        if self.insecure:
            scheme = "http://"
        else:
            scheme = "https://"
        endpoint = str(self.exporter_endpoint) + ":" + str(self.service_port)

        if self.exporter_protocol == TraceTransportProtocol.HTTP_PROTOBUF:
            endpoint += "/v1/traces"

        return scheme + endpoint


class Override(BaseModel):
    message_bus: Optional[InfrahubMessageBus] = None
    cache: Optional[InfrahubCache] = None


class Settings(BaseSettings):
    """Main Settings Class for the project."""

    main: MainSettings = MainSettings()
    api: ApiSettings = ApiSettings()
    git: GitSettings = GitSettings()
    database: DatabaseSettings = DatabaseSettings()
    broker: BrokerSettings = BrokerSettings()
    cache: CacheSettings = CacheSettings()
    miscellaneous: MiscellaneousSettings = MiscellaneousSettings()
    logging: LoggingSettings = LoggingSettings()
    analytics: AnalyticsSettings = AnalyticsSettings()
    security: SecuritySettings = SecuritySettings()
    storage: StorageSettings = StorageSettings()
    trace: TraceSettings = TraceSettings()
    experimental_features: ExperimentalFeaturesSettings = ExperimentalFeaturesSettings()


def load(config_file_name: str = "infrahub.toml", config_data: Optional[Dict[str, Any]] = None) -> None:
    """Load configuration.

    Configuration is loaded from a config file in toml format that contains the settings,
    or from a dictionary of those settings passed in as "config_data"
    """
    global SETTINGS  # pylint: disable=global-statement

    if config_data:
        SETTINGS = Settings(**config_data)
        return

    if os.path.exists(config_file_name):
        config_string = Path(config_file_name).read_text(encoding="utf-8")
        config_tmp = toml.loads(config_string)

        SETTINGS = Settings(**config_tmp)
        return

    SETTINGS = Settings()


def load_and_exit(config_file_name: str = "infrahub.toml", config_data: Optional[Dict[str, Any]] = None) -> None:
    """Calls load, but wraps it in a try except block.

    This is done to handle a ValidationErorr which is raised when settings are specified but invalid.
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
            print(f"  {'/'.join(error['loc'])} | {error['msg']} ({error['type']})")
        sys.exit(1)


OVERRIDE: Override = Override()
