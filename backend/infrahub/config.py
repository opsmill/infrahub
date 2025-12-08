from __future__ import annotations

import os
import re
import ssl
import sys
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from infrahub_sdk.utils import generate_uuid
from pydantic import (
    AliasChoices,
    BaseModel,
    EmailStr,
    Field,
    PrivateAttr,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Self

from infrahub.constants.database import DatabaseType
from infrahub.exceptions import InitializationError, ProcessingError
from infrahub.log import get_logger
from infrahub.tls.context_builder import TlsContextBuilder

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.adapters.message_bus import InfrahubMessageBus
    from infrahub.services.adapters.workflow import InfrahubWorkflow


log = get_logger()

# Neo4j naming rules: 3-63 chars, alphanumeric start/end, dots and dashes allowed within.
VALID_DATABASE_NAME_REGEX = r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$"
THIRTY_DAYS_IN_SECONDS = 3600 * 24 * 30


def default_cors_allow_methods() -> list[str]:
    return ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]


def default_cors_allow_headers() -> list[str]:
    return ["accept", "authorization", "content-type", "user-agent", "x-csrftoken", "x-requested-with"]


def default_append_git_suffix_domains() -> list[str]:
    return ["github.com", "gitlab.com"]


class EnterpriseFeatures(StrEnum):
    PROPOSED_CHANGE_REQUIRE_APPROVAL = "proposed_change_require_approval"
    REVOKE_PROPOSED_CHANGE_APPROVALS = "revoke_proposed_change_approvals"
    LOG_FORWARDING = "log_forwarding"
    LDAP = "ldap"


class UserInfoMethod(StrEnum):
    POST = "post"
    GET = "get"


class SSOProtocol(StrEnum):
    OAUTH2 = "oauth2"
    OIDC = "oidc"


class Oauth2Provider(StrEnum):
    GOOGLE = "google"
    PROVIDER1 = "provider1"
    PROVIDER2 = "provider2"


class OIDCProvider(StrEnum):
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


class StorageDriver(StrEnum):
    FileSystemStorage = "local"
    InfrahubS3ObjectStorage = "s3"


class TraceExporterType(StrEnum):
    CONSOLE = "console"
    OTLP = "otlp"
    # JAEGER = "jaeger"
    # ZIPKIN = "zipkin"


class TraceTransportProtocol(StrEnum):
    GRPC = "grpc"
    HTTP_PROTOBUF = "http/protobuf"
    # HTTP_JSON = "http/json"


class BrokerDriver(StrEnum):
    RabbitMQ = "rabbitmq"
    NATS = "nats"
    Redis = "redis"

    @property
    def driver_module_path(self) -> str:
        match self:
            case BrokerDriver.NATS:
                return "infrahub.services.adapters.message_bus.nats"
            case BrokerDriver.RabbitMQ:
                return "infrahub.services.adapters.message_bus.rabbitmq"
            case BrokerDriver.Redis:
                return "infrahub.services.adapters.message_bus.redis"

    @property
    def driver_class_name(self) -> str:
        match self:
            case BrokerDriver.NATS:
                return "NATSMessageBus"
            case BrokerDriver.RabbitMQ:
                return "RabbitMQMessageBus"
            case BrokerDriver.Redis:
                return "RedisMessageBus"


class CacheDriver(StrEnum):
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


class WorkflowDriver(StrEnum):
    LOCAL = "local"
    WORKER = "worker"


class ExtraLogLevel(StrEnum):
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
    diff_update_after_merge: bool = Field(
        default=True,
        description="When enabled, diff updates are triggered for active branches after a branch merge.",
    )
    delete_branch_after_merge: bool = Field(
        default=False,
        description="When enabled, the Infrahub branch is automatically deleted after a successful merge.",
    )

    @field_validator("docs_index_path", mode="before")
    @classmethod
    def convert_to_path(cls, value: Path | str) -> Path:
        return Path(value) if isinstance(value, str) else value

    @property
    def infrahub_address(self) -> str:
        """This is the address that the Prefect worker will use to connect to Infrahub API.

        Raises:
            InitializationError: When `internal_address` has not been configured.

        """
        if self.internal_address:
            return self.internal_address

        raise InitializationError()


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
    max_file_size: int = Field(default=50, ge=1, description="Maximum file size in MB for file uploads")


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_DB_")
    db_type: DatabaseType = Field(
        default=DatabaseType.NEO4J, validation_alias=AliasChoices("INFRAHUB_DB_TYPE", "db_type")
    )
    protocol: str = "bolt"
    username: str = "neo4j"
    password: str = "admin"
    address: str = Field(
        default="localhost",
        description="Database host, or a comma-separated list of cluster members in 'host[:port]' format. "
        "Members without an explicit port use the value of the port setting.",
    )
    port: int = 7687
    database: str | None = Field(default=None, pattern=VALID_DATABASE_NAME_REGEX, description="Name of the database")
    policy: str | None = Field(default=None, description="Routing policy for database connections")
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    tls_insecure: bool = Field(default=False, description="Indicates if TLS certificates are verified")
    tls_ca_file: str | None = Field(default=None, description="File path to CA cert or bundle in PEM format")
    query_size_limit: int = Field(
        default=5_000,
        ge=1,
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
    retry_base_delay: float = Field(
        default=0.1, ge=0, description="Base delay in seconds for exponential backoff on transaction retries."
    )
    retry_max_delay: float = Field(
        default=2.0, ge=0, description="Maximum delay in seconds for exponential backoff on transaction retries."
    )
    retry_jitter_max: float = Field(
        default=0.1, ge=0, description="Maximum jitter in seconds added to retry delay to avoid thundering herd."
    )
    max_concurrent_queries: int = Field(
        default=0, ge=0, description="Maximum number of concurrent queries that can run (0 means unlimited)."
    )
    max_concurrent_queries_delay: float = Field(
        default=0.01, ge=0, description="Delay to add when max_concurrent_queries is reached."
    )
    path_traversal_query_timeout: float = Field(
        default=30,
        ge=1,
        description=(
            "Server-side transaction timeout in seconds for each point-to-point path-traversal "
            "query. Point-to-point traversal runs many small queries one depth at a time, so a "
            "single query that exceeds this budget marks a doomed search: it is aborted and the "
            "shallower paths found so far are returned with a truncation depth, rather than the "
            "whole request failing."
        ),
    )
    reachable_nodes_query_timeout: float = Field(
        default=75,
        ge=1,
        description=(
            "Server-side transaction timeout in seconds for reachable-nodes queries; "
            "the query is aborted once it is exceeded."
        ),
    )

    @property
    def address_members(self) -> list[str]:
        """All members defined in the address setting, in 'host[:port]' format."""
        return [member.strip() for member in self.address.split(",") if member.strip()]

    @property
    def database_uri(self) -> str:
        """Constructs the database URI based on the configuration settings.

        When multiple members are configured, only the first one is part of the URI;
        the others are made available to the driver through a custom address resolver.
        """
        member = self.address_members[0] if self.address_members else self.address
        host, member_port = self._split_member(member)
        base_uri = f"{self.protocol}://{host}:{member_port or self.port}"
        if self.policy is not None:
            return f"{base_uri}?policy={self.policy}"
        return base_uri

    @staticmethod
    def _split_member(member: str) -> tuple[str, int | None]:
        """Split a 'host[:port]' member into host and optional port, supporting bracketed IPv6 hosts."""
        if member.startswith("["):
            host, _, rest = member.partition("]")
            host += "]"
            if rest.startswith(":") and rest[1:].isdigit():
                return host, int(rest[1:])
            return host, None
        if member.count(":") == 1:
            host, _, port_str = member.partition(":")
            if port_str.isdigit():
                return host, int(port_str)
        return member, None

    @property
    def database_name(self) -> str:
        return self.database or self.db_type.value


class DevelopmentSettings(BaseSettings):
    """The development settings are only relevant for local development."""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_DEV_")

    frontend_redirect_sso: bool = Field(
        default=False,
        description="Indicates of the frontend should be responsible for the SSO redirection",
    )
    allow_enterprise_configuration: bool = Field(
        default=False,
        description="Allow enterprise configuration in development mode, this will not enable the features just allow the configuration.",
    )
    git_credential_helper: str = Field(
        default="infrahub-git-credential",
        description="Location of git credential helper",
    )


class BrokerSettings(BaseSettings):
    """Configuration settings for the message bus."""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_BROKER_")
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
    clean_up_deadlocks_interval_mins: int = Field(
        default=15,
        ge=1,
        description="Age threshold in minutes: locks older than this and owned by inactive workers are deleted by the cleanup task.",
    )
    init_lock_ttl_mins: int = Field(
        default=20,
        ge=1,
        description=(
            "Time-to-live in minutes for the global initialization locks. If a worker dies while holding one, "
            "the lock auto-expires after this period so Infrahub can recover on its own. "
            "Only enforced with the Redis cache driver."
        ),
    )

    @property
    def service_port(self) -> int:
        default_ports: int = 6379
        if self.driver == CacheDriver.NATS:
            return self.port or 4222
        return self.port or default_ports


class WorkflowSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_WORKFLOW_")
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
    flow_run_count_cache_threshold: int = Field(
        default=100_000,
        ge=0,
        description="Threshold for caching flow run counts (0 to always cache, higher values to disable)",
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
    import_sync_branch_names: list[str] = Field(
        default_factory=list,
        description=(
            "Names or regex of branches to be created in infrahub during import "
            "e.g. 'infrahub/.*', 'release/.*', '^branch-'. "
            "Note: other branches created with sync with git will be imported also"
        ),
    )
    user_name: str = Field(
        default="Infrahub",
        description=(
            "User name of the git user. This will be used as the user name when Infrahub commits code to a repository"
        ),
    )
    user_email: EmailStr = Field(
        default="infrahub@opsmill.com",
        description=(
            "Email of the git user. This will be used as the user email when Infrahub commits code to a repository"
        ),
    )
    global_config_file: str = Field(
        default="/opt/infrahub/.gitconfig",
        description=(
            "The location of the git config file. "
            "This will be set as the system `GIT_CONFIG_GLOBAL` environment variable "
            "if the environment variable is not initially set"
        ),
    )
    use_explicit_merge_commit: bool = Field(
        default=False, description="Whether to allow explicit merge commits when infrahub merges branches"
    )
    delete_git_branch_after_merge: bool = Field(
        default=False,
        description="When enabled, the corresponding Git branch is deleted after the Infrahub branch is deleted. "
        "Requires delete_branch_after_merge to be enabled.",
    )

    @model_validator(mode="after")
    def validate_sync_branch_names(self) -> Self:
        for branch_filter in self.import_sync_branch_names:
            try:
                re.compile(branch_filter)
            except re.error as exc:
                raise ValueError(
                    f"Invalid regex pattern for import_sync_branch_names: '{branch_filter}' — {exc}"
                ) from exc
        return self


class HTTPSettings(BaseSettings):
    """The HTTP settings control how Infrahub interacts with external HTTP servers. This can be things like webhooks and OAuth2 providers."""

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
            TlsContextBuilder.build(
                insecure=self.tls_insecure, ca_bundle=self.tls_ca_bundle, force_verify=bool(self.tls_ca_bundle)
            )
        except ssl.SSLError as exc:
            raise ValueError(f"Unable load CA bundle from {self.tls_ca_bundle}: {exc}") from exc

        return self


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
    """Baseclass for typing."""

    icon: str = Field(default="mdi:account-key")
    display_label: str = Field(default="Single Sign on")
    userinfo_method: UserInfoMethod = Field(default=UserInfoMethod.GET)
    pkce_enabled: bool = Field(
        default=True, description="Enable PKCE (RFC 7636) with S256 method for authorization code flow"
    )
    id_token_verify_signature: bool = Field(
        default=True,
        description="Verify the cryptographic signature, audience and issuer of the OIDC id_token.",
    )
    groups_claim: str = Field(
        default="groups",
        description=(
            "Top-level key in the IdP claim payload from which the user's groups are read. "
            "Defaults to `groups`. Set per provider when your IdP emits group memberships "
            "under a different claim name (e.g., `roles`)."
        ),
    )

    @model_validator(mode="after")
    def warn_when_signature_verification_disabled(self) -> Self:
        if not self.id_token_verify_signature:
            log.warning(
                "OIDC id_token verification is disabled; any token presented to the callback will be trusted.",
                provider=self.__class__.__name__,
            )
        return self

    @field_validator("groups_claim")
    @classmethod
    def _validate_groups_claim(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("groups_claim must not be empty or whitespace-only")
        return value.strip()


class SecurityOIDCSettings(SecurityOIDCBaseSettings):
    client_id: str = Field(..., description="Client ID of the application created in the auth provider")
    client_secret: str | None = Field(default=None, description="Client secret as defined in auth provider")
    discovery_url: str = Field(..., description="The OIDC discovery URL xyz/.well-known/openid-configuration")
    scopes: list[str] = Field(default_factory=_default_scopes)


class SecurityOIDCGoogle(SecurityOIDCSettings):
    """Settings for the custom OIDC provider."""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OIDC_GOOGLE_")

    discovery_url: str = Field(default="https://accounts.google.com/.well-known/openid-configuration")
    icon: str = Field(default="mdi:google")
    display_label: str = Field(default="Google")
    fetch_groups: bool = Field(
        default=False,
        description="Whether to use Cloud Identity API to fetch user groups. Note: requires additional scope: https://www.googleapis.com/auth/cloud-identity.groups.readonly",
    )
    cloudidentity_url: str = Field(
        default="https://cloudidentity.googleapis.com/v1/groups/-/memberships:searchDirectGroups",
        description="Google Cloud endpoint for Cloud Identity. Using searchDirectGroups by default because it is available for the Free plan",
    )


class SecurityOIDCProvider1(SecurityOIDCSettings):
    """Settings for the custom OIDC provider."""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OIDC_PROVIDER1_")


class SecurityOIDCProvider2(SecurityOIDCSettings):
    """Settings for the custom OIDC provider."""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OIDC_PROVIDER2_")


class SecurityOIDCProviderSettings(BaseModel):
    """This class is meant to facilitate configuration of OIDC providers when loading configuration from a infrahub.toml file."""

    google: SecurityOIDCGoogle | None = Field(default=None)
    provider1: SecurityOIDCProvider1 | None = Field(default=None)
    provider2: SecurityOIDCProvider2 | None = Field(default=None)


class SecurityOAuth2BaseSettings(BaseSettings):
    """Baseclass for typing."""

    icon: str = Field(default="mdi:account-key")
    userinfo_method: UserInfoMethod = Field(default=UserInfoMethod.GET)
    pkce_enabled: bool = Field(
        default=True, description="Enable PKCE (RFC 7636) with S256 method for authorization code flow"
    )
    groups_claim: str = Field(
        default="groups",
        description=(
            "Top-level key in the IdP claim payload from which the user's groups are read. "
            "Defaults to `groups`. Set per provider when your IdP emits group memberships "
            "under a different claim name (e.g., `roles`)."
        ),
    )

    @field_validator("groups_claim")
    @classmethod
    def _validate_groups_claim(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("groups_claim must not be empty or whitespace-only")
        return value.strip()


class SecurityOAuth2Settings(SecurityOAuth2BaseSettings):
    """Common base for Oauth2 providers."""

    client_id: str = Field(..., description="Client ID of the application created in the auth provider")
    client_secret: str | None = Field(default=None, description="Client secret as defined in auth provider")
    authorization_url: str = Field(...)
    token_url: str = Field(...)
    userinfo_url: str = Field(...)
    scopes: list[str] = Field(default_factory=_default_scopes)
    display_label: str = Field(default="Single Sign on")


class SecurityOAuth2Provider1(SecurityOAuth2Settings):
    """Common base for Oauth2 providers."""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OAUTH2_PROVIDER1_")


class SecurityOAuth2Provider2(SecurityOAuth2Settings):
    """Common base for Oauth2 providers."""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OAUTH2_PROVIDER2_")


class SecurityOAuth2Google(SecurityOAuth2Settings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_OAUTH2_GOOGLE_")
    authorization_url: str = Field(default="https://accounts.google.com/o/oauth2/auth")
    token_url: str = Field(default="https://oauth2.googleapis.com/token")
    userinfo_url: str = Field(default="https://www.googleapis.com/oauth2/v3/userinfo")
    icon: str = Field(default="mdi:google")
    display_label: str = Field(default="Google")
    fetch_groups: bool = Field(
        default=False,
        description="Whether to use Cloud Identity API to fetch user groups. Note: requires additional scopes: https://www.googleapis.com/auth/cloud-identity.groups.readonly",
    )
    cloudidentity_url: str = Field(
        default="https://cloudidentity.googleapis.com/v1/groups/-/memberships:searchDirectGroups",
        description="Google Cloud endpoint for Cloud Identity. Using searchDirectGroups by default because it is available for the Free plan",
    )


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
    value_db_index: bool = Field(
        default=False,
        deprecated="This setting has no effect and will be removed in a future version.",
    )


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
        default=True, description="Indicates if untrusted Jinja2 filters should be disallowed for computed attributes"
    )
    _oauth2_settings: dict[str, SecurityOAuth2Settings] = PrivateAttr(default_factory=dict)
    _oidc_settings: dict[str, SecurityOIDCSettings] = PrivateAttr(default_factory=dict)
    sso_user_default_group: str | None = Field(
        default=None,
        description="Name of the group assigned to an SSO user on their first login when the identity "
        "provider supplies no group claims. Applied only when the account is first created; it is "
        "not re-applied on subsequent logins, so removing a user from this group is not undone.",
    )
    auto_create_groups_filter: str | list[str] | None = Field(
        default=None,
        description="Regex(es) that decide which external identity-provider group claims become "
        "Infrahub groups. Accepts one regex or a list; the first matching pattern wins. "
        "Use a named capture group `(?P<name>...)` to set the group name; otherwise the "
        "full claim is used. Leave empty to disable auto-creation.",
    )
    auto_create_groups_max_per_login: int = Field(
        default=50,
        ge=1,
        description="Maximum number of groups that can be auto-created during a single login. "
        "Once reached, further new groups are skipped (with a warning) but the login "
        "still succeeds. Adding the user to groups that already exist is not limited.",
    )
    _auto_create_groups_filter_patterns: tuple[re.Pattern[str], ...] = PrivateAttr(default_factory=tuple)

    @field_validator("auto_create_groups_filter", mode="after")
    @classmethod
    def _validate_auto_create_groups_filter(cls, value: str | list[str] | None) -> str | list[str] | None:
        """Validate that every configured regex compiles cleanly at startup.

        Empty / unset values are accepted unchanged — they mean "feature off".

        Raises:
            ValueError: When a configured regex pattern fails to compile. Pydantic surfaces the
                error attached to the setting name.

        """
        if value is None:
            return value

        raw_patterns: list[str] = [value] if isinstance(value, str) else list(value)
        raw_patterns = [stripped for p in raw_patterns if (stripped := p.strip())]
        for index, pattern in enumerate(raw_patterns):
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"auto_create_groups_filter[{index}]: invalid regex {pattern!r}: {exc}") from exc
        return value

    @model_validator(mode="after")
    def _compile_auto_create_groups_filter_patterns(self) -> Self:
        self.recompile_auto_create_groups_filter_patterns()
        return self

    def recompile_auto_create_groups_filter_patterns(self) -> None:
        """Compile `auto_create_groups_filter` into the private patterns tuple.

        Plain method (not a validator) so callers that mutate `auto_create_groups_filter`
        on the live settings singleton — e.g. test fixtures — can re-trigger compilation
        without going through Pydantic's validator chain.
        """
        if self.auto_create_groups_filter is None:
            self._auto_create_groups_filter_patterns = ()
            return

        raw_patterns: list[str]
        if isinstance(self.auto_create_groups_filter, str):
            raw_patterns = [self.auto_create_groups_filter]
        else:
            raw_patterns = list(self.auto_create_groups_filter)
        raw_patterns = [stripped for p in raw_patterns if (stripped := p.strip())]
        self._auto_create_groups_filter_patterns = tuple(re.compile(p) for p in raw_patterns)

    @property
    def auto_create_groups_filter_patterns(self) -> tuple[re.Pattern[str], ...]:
        """Compiled filter patterns. Empty tuple means the feature is off."""
        return self._auto_create_groups_filter_patterns

    @property
    def auto_create_groups_enabled(self) -> bool:
        """True iff at least one usable filter pattern is configured."""
        return len(self._auto_create_groups_filter_patterns) > 0

    sso_account_name_fallback: bool = Field(
        default=True,
        description=(
            "When enabled, an SSO login that has no linked identity and matches an existing account by "
            "display name claims that account, as long as it has not already been linked to another "
            "identity. When disabled, such a login always provisions a separate account instead of "
            "reusing an existing one."
        ),
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


class SyslogProtocol(StrEnum):
    TCP = "tcp"
    UDP = "udp"


class SyslogFormat(StrEnum):
    RFC5424 = "rfc5424"
    RFC3164 = "rfc3164"


class TcpFraming(StrEnum):
    NEWLINE = "newline"
    OCTET_COUNTING = "octet-counting"


class LogForwardingDestinationType(StrEnum):
    SYSLOG = "syslog"


class LogForwardingDestination(BaseModel):
    name: str = Field(description="Unique name for the destination, used in all observability output.")
    type: LogForwardingDestinationType = Field(
        default=LogForwardingDestinationType.SYSLOG, description="Destination type."
    )
    host: str = Field(description="Destination host or IP address.")
    port: int | None = Field(
        default=None, ge=1, le=65535, description="Destination port number. Defaults to 6514 for TLS, 514 otherwise."
    )
    protocol: SyslogProtocol = Field(default=SyslogProtocol.UDP, description="Transport protocol (tcp or udp).")
    format: SyslogFormat = Field(default=SyslogFormat.RFC5424, description="Syslog format standard.")
    tcp_framing: TcpFraming = Field(
        default=TcpFraming.NEWLINE, description="TCP framing method (newline or octet-counting)."
    )
    tls_enabled: bool = Field(default=False, description="Enable TLS encryption for TCP connections.")
    tls_ca_bundle: str | None = Field(
        default=None, description="Path or PEM string for CA bundle to validate syslog server certificate."
    )
    queue_size: int = Field(default=10000, ge=1, description="Maximum number of messages in the per-destination queue.")
    max_reconnect_interval: int = Field(
        default=60, ge=1, description="Maximum reconnection backoff interval in seconds."
    )
    shutdown_drain_timeout: int = Field(
        default=10, ge=0, description="Seconds to wait for queue drain on graceful shutdown."
    )
    forward_application_logs: bool = Field(
        default=False, description="Forward application log messages to this destination."
    )
    min_log_severity: ExtraLogLevel = Field(
        default=ExtraLogLevel.WARNING,
        description="Minimum Python log severity to forward when application log forwarding is enabled.",
    )

    @property
    def service_port(self) -> int:
        if self.port:
            return self.port
        if self.tls_enabled:
            return 6514
        return 514

    @model_validator(mode="after")
    def validate_tls_protocol(self) -> Self:
        if self.tls_enabled and self.protocol == SyslogProtocol.UDP:
            raise ValueError("TLS is only supported with TCP protocol, not UDP.")
        return self


_DESTINATION_NAME_RE = re.compile(r"^[a-z0-9_]+$")


def _load_destination_from_env(name: str) -> LogForwardingDestination:
    """Build a LogForwardingDestination by scanning os.environ for keys matching.

    INFRAHUB_LOG_FORWARDING_DESTINATION_{NAME_UPPER}_{FIELD_UPPER}.

    """
    prefix = f"INFRAHUB_LOG_FORWARDING_DESTINATION_{name.upper()}_"
    valid_field_names = set(LogForwardingDestination.model_fields.keys()) - {"name"}
    fields: dict[str, Any] = {"name": name}
    for env_key, env_val in os.environ.items():
        if env_key.upper().startswith(prefix):
            suffix = env_key[len(prefix) :].lower()
            if suffix in valid_field_names:
                fields[suffix] = env_val
    return LogForwardingDestination.model_validate(fields)


class LogForwardingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_LOG_FORWARDING_")
    hostname: str | None = Field(
        default=None,
        description="Hostname to use in syslog message headers. If not set, defaults to the system FQDN.",
    )
    destination_names: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description=(
            "Comma-separated list of destination names to load from per-destination environment variables "
            "(e.g. `INFRAHUB_LOG_FORWARDING_DESTINATION_PRIMARY_HOST` where `PRIMARY` is the destination name). "
            "Names must match `[a-z0-9_]+`. Mutually exclusive with `destinations`."
        ),
    )
    destinations: list[LogForwardingDestination] = Field(
        default_factory=list,
        description="List of log forwarding destinations. (Enterprise only: not available in the community version.)",
    )

    @field_validator("destination_names", mode="before")
    @classmethod
    def _split_destination_names(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [n.strip() for n in v.split(",") if n.strip()]
        return v

    @model_validator(mode="after")
    def _materialize_destinations_from_env(self) -> Self:
        if not self.destination_names:
            return self
        for name in self.destination_names:
            if not _DESTINATION_NAME_RE.match(name):
                raise ValueError(
                    f"Invalid log forwarding destination name '{name}': names configured via "
                    "INFRAHUB_LOG_FORWARDING_DESTINATION_NAMES must match [a-z0-9_]+ (lowercase letters, "
                    "digits, and underscores only)."
                )
        loaded = [_load_destination_from_env(name) for name in self.destination_names]
        # Re-run uniqueness check (covers duplicates within destination_names itself).
        self.__class__.validate_unique_names(loaded)
        # in case destinations have already been loaded
        if self.destinations == loaded:
            return self
        # if destinations already exist and != loaded, they must have be set in different places
        # with different values
        if self.destinations:
            raise ValueError(
                "INFRAHUB_LOG_FORWARDING_DESTINATION_NAMES cannot be combined with explicit `destinations` "
                "(set via INFRAHUB_LOG_FORWARDING_DESTINATIONS or infrahub.toml). Use one mechanism, not both."
            )
        self.destinations = loaded
        return self

    @field_validator("destinations")
    @classmethod
    def validate_unique_names(cls, v: list[LogForwardingDestination]) -> list[LogForwardingDestination]:
        unique_names = {d.name for d in v}
        if len(unique_names) == len(v):
            return v
        all_names = [d.name for d in v]
        duplicate_names = {name for name in unique_names if all_names.count(name) > 1}
        sorted_dupes = ", ".join(sorted(duplicate_names))
        raise ValueError(f"Destination names must be unique; duplicates found: {sorted_dupes}")

    @property
    def enterprise_features(self) -> list[EnterpriseFeatures]:
        """Returns enterprise features enabled by log forwarding configuration."""
        if any(d.type == LogForwardingDestinationType.SYSLOG for d in self.destinations):
            return [EnterpriseFeatures.LOG_FORWARDING]
        return []


class PolicySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_POLICY_")
    required_proposed_change_approvals: int = Field(
        default=0,
        ge=0,
        description="Number of approvals required for proposed changes. (Enterprise only: not available in the community version.)",
    )
    revoke_proposed_change_approvals: bool = Field(
        default=False,
        description="Boolean indicating whether performing changes on a proposed change branch should revoke existing approvals."
        " (Enterprise only: not available in the community version.)",
    )

    @property
    def enterprise_features(self) -> list[EnterpriseFeatures]:
        """Returns a list of enterprise features that are enabled based on the settings."""
        features = []
        if self.required_proposed_change_approvals > 0:
            features.append(EnterpriseFeatures.PROPOSED_CHANGE_REQUIRE_APPROVAL)
        if self.revoke_proposed_change_approvals:
            features.append(EnterpriseFeatures.REVOKE_PROPOSED_CHANGE_APPROVALS)
        return features


LDAP_DEFAULT_DISPLAY_LABEL = "Sign in with LDAP"
LDAP_DEFAULT_ICON = "mdi:account-key-outline"


class LDAPGroupResolutionStrategy(StrEnum):
    BFS = "bfs"
    AD_IN_CHAIN = "ad_in_chain"


class LDAPTLSMinimumVersion(StrEnum):
    TLS_1_2 = "TLSv1.2"
    TLS_1_3 = "TLSv1.3"


class LDAPInfo(BaseModel):
    enabled: bool = Field(
        default=False,
        description=(
            "True when LDAP sign-in is available on this deployment, meaning "
            "it has been configured and the running edition supports it."
        ),
    )
    display_label: str = Field(
        default=LDAP_DEFAULT_DISPLAY_LABEL,
        description="Text shown on the LDAP sign-in button on the login page.",
    )
    icon: str = Field(
        default=LDAP_DEFAULT_ICON,
        description="Icon shown on the LDAP sign-in button on the login page.",
    )


class LDAPSettings(BaseSettings):
    """LDAP authentication configuration."""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_LDAP_")

    enabled: bool = Field(
        default=False,
        description=(
            "Enable LDAP authentication on this deployment. When turned off, "
            "new LDAP sign-ins are refused; existing sessions are unaffected."
        ),
    )
    servers: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description=(
            "Comma-separated list of LDAP server URIs (e.g. "
            "`ldaps://dc1.example.com:636,ldaps://dc2.example.com:636`). Each "
            "entry is tried in declaration order, falling through to the next "
            "when one is unreachable, so list a primary first and any standby "
            "replicas after it for high availability. URIs must use the `ldap` "
            "or `ldaps` scheme."
        ),
    )

    service_account_dn: str | None = Field(
        default=None,
        description=(
            "Distinguished name of the directory account used to look up users before verifying their credentials."
        ),
    )
    service_account_password: str | None = Field(
        default=None,
        description="Password for the service account used during the user lookup. ",
    )

    user_search_base: str | None = Field(
        default=None,
        description=(
            "Distinguished name of the directory subtree where user entries "
            "are stored, e.g. `OU=Users,DC=corp,DC=example,DC=com`."
        ),
    )
    user_search_filter: str | None = Field(
        default=None,
        description=(
            "LDAP filter used to locate a user entry by their sign-in name. "
            "The `{username}` placeholder is substituted at sign-in time with "
            "the user-supplied login name and is safely escaped to prevent "
            "filter injection. If left empty, a default is generated from "
            "the configured username attribute (`attribute_username`), so "
            "changing the username attribute keeps the filter aligned "
            "automatically."
        ),
    )

    attribute_username: str = Field(
        default="sAMAccountName",
        description=(
            "Name of the LDAP attribute that holds a user's sign-in name. "
            "Defaults to `sAMAccountName` (typical on Active Directory); "
            "`uid` is typical on OpenLDAP."
        ),
    )
    attribute_display_name: str = Field(
        default="displayName",
        description="Name of the LDAP attribute that holds a user's human-readable display name.",
    )
    attribute_disabled: str | None = Field(
        default="userAccountControl",
        description=(
            "Name of an LDAP attribute that signals whether an account is "
            "disabled. Defaults to `userAccountControl` (Active Directory's "
            "mechanism). Leave empty for directories that do not expose an "
            "equivalent attribute; the disabled-account check is then skipped."
        ),
    )
    attribute_disabled_bitmask: int = Field(
        default=0x2,
        ge=1,
        description=(
            "When `attribute_disabled` is set, the integer value of that "
            "attribute is treated as a bitmask; the account is considered "
            "disabled if any of these bits are set. Default `0x2` matches "
            "Active Directory's standard 'account disabled' flag."
        ),
    )

    group_enabled: bool = Field(
        default=False,
        description=(
            "Enable directory group resolution. When turned off, users sign "
            "in successfully but receive no permissions until they are "
            "assigned to local groups manually. When turned on, "
            "`group_base_dn` must be set."
        ),
    )
    group_base_dn: str | None = Field(
        default=None,
        description=(
            "Distinguished name of the directory subtree where group entries "
            "are stored, e.g. `OU=Groups,DC=corp,DC=example,DC=com`. Required "
            "when `group_enabled` is true."
        ),
    )
    group_filter: str = Field(
        default="(member={user_dn})",
        description=(
            "LDAP filter used to look up the groups a user belongs to. The "
            "`{user_dn}` placeholder is substituted with the user's "
            "distinguished name at sign-in time and is safely escaped to "
            "prevent filter injection."
        ),
    )
    group_name_attribute: str = Field(
        default="cn",
        description=(
            "Name of the LDAP attribute on group entries that is read as the "
            "group's name. The value is matched against local group names to "
            "grant the user the matching permissions."
        ),
    )
    group_strategy: LDAPGroupResolutionStrategy = Field(
        default=LDAPGroupResolutionStrategy.BFS,
        description=(
            "How nested-group memberships are resolved. `ad_in_chain` uses "
            "Active Directory's transitive-membership search to retrieve all "
            "nested groups in a single query; it is the fastest option "
            "against AD. `bfs` walks group memberships level by level and "
            "works against any LDAP-compatible directory."
        ),
    )
    group_bfs_max_depth: int = Field(
        default=16,
        ge=10,
        description=(
            "Maximum number of nesting levels to traverse when "
            "`group_strategy` is `bfs`. Has no effect for other strategies. "
            "Cycles in the group structure are detected automatically. "
            "Minimum value is 10."
        ),
    )

    tls_enabled: bool = Field(
        default=False,
        description=(
            "Use an encrypted connection to the LDAP server. Pair with "
            "`ldaps://` server URIs, or set `tls_starttls = true` to upgrade "
            "plain `ldap://` connections."
        ),
    )
    tls_starttls: bool = Field(
        default=False,
        description="Upgrade a plain `ldap://` connection to TLS using STARTTLS instead of connecting via `ldaps://`.",
    )
    tls_ca_bundle: str | None = Field(
        default=None,
        description=(
            "PEM-encoded certificate authority bundle used to verify the LDAP "
            "server's TLS certificate. May be a path to a file or the PEM "
            "contents directly. Checked at startup."
        ),
    )
    tls_insecure: bool = Field(
        default=False,
        description=(
            "Skip TLS certificate validation. Test and development environments only; never enable in production."
        ),
    )
    tls_minimum_version: LDAPTLSMinimumVersion = Field(
        default=LDAPTLSMinimumVersion.TLS_1_2,
        description="Minimum TLS protocol version accepted when connecting to an LDAP server.",
    )

    per_server_timeout: float = Field(
        default=10.0,
        gt=0.0,
        description=(
            "Maximum time, in seconds, to wait for an LDAP server to respond "
            "before treating it as unreachable and trying the next configured "
            "server."
        ),
    )

    display_label: str = Field(
        default=LDAP_DEFAULT_DISPLAY_LABEL,
        description="Text shown on the LDAP sign-in button on the login page.",
    )
    icon: str = Field(
        default=LDAP_DEFAULT_ICON,
        description="Icon shown on the LDAP sign-in button on the login page.",
    )

    @field_validator("servers", mode="before")
    @classmethod
    def _split_servers(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("servers")
    @classmethod
    def _validate_server_uris(cls, v: list[str]) -> list[str]:
        for uri in v:
            if not uri.startswith(("ldap://", "ldaps://")):
                raise ValueError(f"LDAP URI scheme must be 'ldap' or 'ldaps', got: {uri!r}")
            rest = uri.split("://", 1)[1]
            host = rest.split("/", 1)[0].split(":", 1)[0]
            if not host:
                raise ValueError("LDAP URI must include a hostname")
        return v

    @property
    def admin_enabled(self) -> bool:
        return self.enabled and bool(self.servers)

    @model_validator(mode="after")
    def derive_default_user_search_filter(self) -> Self:
        # Tie the filter to the configured username attribute so the two
        # cannot drift. Operators who set their own filter are unaffected.
        if self.user_search_filter is None:
            self.user_search_filter = f"({self.attribute_username}={{username}})"
        return self

    @model_validator(mode="after")
    def validate_tls_configuration(self) -> Self:
        if not self.tls_enabled:
            return self
        if self.tls_insecure and self.tls_ca_bundle is not None:
            raise ValueError("ldap.tls_insecure cannot be combined with ldap.tls_ca_bundle; pick one.")
        try:
            TlsContextBuilder.build(
                insecure=self.tls_insecure, ca_bundle=self.tls_ca_bundle, force_verify=bool(self.tls_ca_bundle)
            )
        except ssl.SSLError as exc:
            raise ValueError(f"Unable to load LDAP CA bundle from {self.tls_ca_bundle}: {exc}") from exc
        return self

    @model_validator(mode="after")
    def check_complete_when_enabled(self) -> Self:
        if not self.enabled:
            return self
        problems: list[str] = []
        if not self.servers:
            problems.append("ldap.servers must be non-empty")
        if not self.service_account_dn:
            problems.append("ldap.service_account_dn is required")
        if not self.service_account_password:
            problems.append("ldap.service_account_password is required")
        if not self.user_search_base:
            problems.append("ldap.user_search_base is required")
        if self.group_enabled and not self.group_base_dn:
            problems.append("ldap.group_base_dn is required when ldap.group_enabled is true")
        if self.tls_starttls and any(uri.startswith("ldaps://") for uri in self.servers):
            problems.append("ldap.tls_starttls cannot be combined with an ldaps:// server URI")
        if problems:
            raise ValueError("Invalid LDAP configuration: " + "; ".join(problems))
        return self

    @property
    def enterprise_features(self) -> list[EnterpriseFeatures]:
        """Returns enterprise features enabled by LDAP configuration."""
        if self.enabled:
            return [EnterpriseFeatures.LDAP]
        return []


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
    def policy(self) -> PolicySettings:
        return self.active_settings.policy

    @property
    def security(self) -> SecuritySettings:
        return self.active_settings.security

    @property
    def ldap(self) -> LDAPSettings:
        return self.active_settings.ldap

    @property
    def storage(self) -> StorageSettings:
        return self.active_settings.storage

    @property
    def trace(self) -> TraceSettings:
        return self.active_settings.trace

    @property
    def experimental_features(self) -> ExperimentalFeaturesSettings:
        return self.active_settings.experimental_features

    @property
    def enterprise_features(self) -> list[EnterpriseFeatures]:
        """Returns a list of enterprise features that are enabled based on the settings."""
        return self.active_settings.enterprise_features


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
    policy: PolicySettings = PolicySettings()
    security: SecuritySettings = SecuritySettings()
    ldap: LDAPSettings = LDAPSettings()
    storage: StorageSettings = StorageSettings()
    trace: TraceSettings = TraceSettings()
    experimental_features: ExperimentalFeaturesSettings = ExperimentalFeaturesSettings()
    log_forwarding: LogForwardingSettings = LogForwardingSettings()

    @model_validator(mode="after")
    def validate_git_branch_deletion_requires_branch_deletion(self) -> Self:
        if self.git.delete_git_branch_after_merge and not self.main.delete_branch_after_merge:
            raise ValueError("'delete_git_branch_after_merge' requires 'delete_branch_after_merge' to be enabled")
        return self

    @property
    def enterprise_features(self) -> list[EnterpriseFeatures]:
        """Returns a list of enterprise features that are enabled based on the settings."""
        return self.policy.enterprise_features + self.log_forwarding.enterprise_features + self.ldap.enterprise_features


def load(config_file_name: Path | str = "infrahub.toml", config_data: dict[str, Any] | None = None) -> Settings:
    """Load configuration.

    Configuration is loaded from a configuration file in toml format that contains the settings,
    or from a dictionary of those settings passed in as "config_data"
    """
    config_file = Path(config_file_name)

    if config_data:
        return Settings(**config_data)

    if config_file.exists():
        config_string = config_file.read_text(encoding="utf-8")
        config_tmp = tomllib.loads(config_string)

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
