from __future__ import annotations

import os
import os.path
import sys
from pathlib import Path
from typing import Dict, List, Optional

import toml
from pydantic import BaseSettings, Field, ValidationError

from infrahub_client.utils import generate_uuid

SETTINGS: Settings = None

VALID_DATABASE_NAME_REGEX = r"^[a-z][a-z0-9\.]+$"
THIRTY_DAYS_IN_SECONDS = 3600 * 24 * 30


class MainSettings(BaseSettings):
    default_branch: str = "main"
    # default_account: str = "default"
    # default_account_perm: str = "CAN_READ"

    internal_address: str = "http://localhost:8000"
    allow_anonymous_access: bool = Field(
        default=True, description="Indicates if the system allows anonymous read access"
    )

    class Config:
        env_prefix = "INFRAHUB_"
        case_sensitive = False


class DatabaseSettings(BaseSettings):
    protocol: str = "neo4j"
    username: str = "neo4j"
    password: str = "admin"
    address: str = "localhost"
    port: int = 7687
    database: str = Field(
        default="infrahub", regex=VALID_DATABASE_NAME_REGEX, description="Name of the database in Neo4j"
    )

    class Config:
        """Additional parameters to automatically map environment variables to some settings."""

        fields = {
            "protocol": {"env": "NEO4J_PROTOCOL"},
            "username": {"env": "NEO4J_USERNAME"},
            "password": {"env": "NEO4J_PASSWORD"},
            "address": {"env": "NEO4J_ADDRESS"},
            "port": {"env": "NEO4J_PORT"},
            "database": {"env": "NEO4J_DATABASE"},
        }


class BrokerSettings(BaseSettings):
    enable: bool = True
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    username: str = "infrahub"
    password: str = "infrahub"
    address: str = "localhost"
    port: Optional[int] = Field(
        default=None, min=1, max=65535, description="Specified if running on a non default port."
    )
    namespace: str = "infrahub"

    @property
    def service_port(self) -> int:
        default_ports: Dict[bool, int] = {True: 5671, False: 5672}
        return self.port or default_ports[self.tls_enabled]

    class Config:
        env_prefix = "INFRAHUB_BROKER_"
        case_sensitive = False


class ApiSettings(BaseSettings):
    cors_allow_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]


class GitSettings(BaseSettings):
    repositories_directory: str = "repositories"


class MiscellaneousSettings(BaseSettings):
    print_query_details: bool = False


class RemoteLoggingSettings(BaseSettings):
    enable: bool = False
    frontend_dsn: Optional[str] = None
    api_server_dsn: Optional[str] = None
    git_agent_dsn: Optional[str] = None

    class Config:
        env_prefix = "INFRAHUB_LOGGING_REMOTE_"
        case_sensitive = False


class LoggingSettings(BaseSettings):
    remote: RemoteLoggingSettings = RemoteLoggingSettings()


class AnalyticsSettings(BaseSettings):
    enable: bool = True
    address: Optional[str] = None
    api_key: Optional[str] = None

    class Config:
        env_prefix = "INFRAHUB_ANALYTICS_"
        case_sensitive = False


class ExperimentalFeaturesSettings(BaseSettings):
    pull_request: bool = False
    ignore_authentication_requirements: bool = Field(
        default=True,
        description="If set to true operations that would have been denied due to lack of authentication still works.",
    )

    class Config:
        env_prefix = "INFRAHUB_EXPERIMENTAL_"
        case_sensitive = False


class SecuritySettings(BaseSettings):
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

    class Config:
        env_prefix = "INFRAHUB_SECURITY_"
        case_sensitive = False


class Settings(BaseSettings):
    """Main Settings Class for the project."""

    main: MainSettings = MainSettings()
    api: ApiSettings = ApiSettings()
    git: GitSettings = GitSettings()
    database: DatabaseSettings = DatabaseSettings()
    broker: BrokerSettings = BrokerSettings()
    miscellaneous: MiscellaneousSettings = MiscellaneousSettings()
    logging: LoggingSettings = LoggingSettings()
    analytics: AnalyticsSettings = AnalyticsSettings()
    security: SecuritySettings = SecuritySettings()
    experimental_features: ExperimentalFeaturesSettings = ExperimentalFeaturesSettings()


def load(config_file_name="infrahub.toml", config_data=None):
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


def load_and_exit(config_file_name="infrahub.toml", config_data=None):
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
