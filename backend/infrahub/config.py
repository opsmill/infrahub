from __future__ import annotations

import os
import os.path
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import toml
from infrahub_sdk import generate_uuid
from pydantic import AliasChoices, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from infrahub.database.constants import DatabaseType
from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.adapters.message_bus import InfrahubMessageBus


VALID_DATABASE_NAME_REGEX = r"^[a-z][a-z0-9\.]+$"
THIRTY_DAYS_IN_SECONDS = 3600 * 24 * 30


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
    docs_index_path: str = Field(
        default="/opt/infrahub/docs/build/search-index.json",
        description="Full path of saved json containing pre-indexed documentation",
    )
    internal_address: str = "http://localhost:8000"
    allow_anonymous_access: bool = Field(
        default=True, description="Indicates if the system allows anonymous read access"
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
    access_key_id: str = Field(default="", validation_alias="AWS_ACCESS_KEY_ID")
    secret_access_key: str = Field(default="", validation_alias="AWS_SECRET_ACCESS_KEY")
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
        default=True, alias="AWS_S3_US_SSL", validation_alias=AliasChoices("INFRAHUB_STORAGE_USE_SSL", "AWS_S3_US_SSL")
    )
    default_acl: str = Field(
        default="",
        alias="AWS_DEFAULT_ACL",
        validation_alias=AliasChoices("INFRAHUB_STORAGE_DEFAULT_ACL", "AWS_DEFAULT_ACL"),
    )
    querystring_auth: bool = Field(
        default=False,
        alias="AWS_QUERYSTRING_AUTH",
        validation_alias=AliasChoices("INFRAHUB_STORAGE_QUERYTSTRING_AUTH", "AWS_QUERYSTRING_AUTH"),
    )
    custom_domain: str = Field(
        default="",
        alias="AWS_S3_CUSTOM_DOMAIN",
        validation_alias=AliasChoices("INFRAHUB_STORAGE_CUSTOM_DOMAIN", "AWS_S3_CUSTOM_DOMAIN"),
    )


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_STORAGE")
    driver: StorageDriver = StorageDriver.FileSystemStorage
    local: FileSystemStorageSettings = FileSystemStorageSettings()
    s3: S3StorageSettings = S3StorageSettings()


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_DB_")
    db_type: DatabaseType = Field(
        default=DatabaseType.MEMGRAPH, validation_alias=AliasChoices("INFRAHUB_DB_TYPE", "db_type")
    )
    protocol: str = "bolt"
    username: str = "neo4j"
    password: str = "admin"
    address: str = "localhost"
    port: int = 7687
    database: Optional[str] = Field(default=None, pattern=VALID_DATABASE_NAME_REGEX, description="Name of the database")
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
    virtualhost: str = Field(default="/", description="The virtual host to connect to")

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
    sync_interval: int = Field(
        default=10, ge=0, description="Time (in seconds) between git repositories synchronizations"
    )


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


@dataclass
class Override:
    message_bus: Optional[InfrahubMessageBus] = None
    cache: Optional[InfrahubCache] = None


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
    def miscellaneous(self) -> MiscellaneousSettings:
        return self.active_settings.miscellaneous

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

    if config_data:
        SETTINGS.settings = Settings(**config_data)
        return

    if os.path.exists(config_file_name):
        config_string = Path(config_file_name).read_text(encoding="utf-8")
        config_tmp = toml.loads(config_string)

        SETTINGS.settings = Settings(**config_tmp)
        return

    SETTINGS.settings = Settings()


def load_and_exit(config_file_name: str = "infrahub.toml", config_data: Optional[Dict[str, Any]] = None) -> None:
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
