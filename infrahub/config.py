"""Config Clas."""
import os
import os.path
import sys
from pathlib import Path

import toml
from pydantic import BaseSettings, Field, ValidationError


SETTINGS = None

VALID_DATABASE_NAME_REGEX = r"^[a-z][a-z0-9\.]+$"


class MainSettings(BaseSettings):

    default_branch: str = "main"
    default_account: str = "default"
    default_account_perm: str = "CAN_READ"

    print_query_details: bool = False

    repositories_directory: str = "repositories"

    class Config:
        """Additional parameters to automatically map environment variable to some settings."""

        fields = {
            "default_branch": {"env": "infrahub_default_branch"},
        }


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
        """Additional parameters to automatically map environment variable to some settings."""

        fields = {
            "protocol": {"env": "NEO4J_PROTOCOL"},
            "username": {"env": "NEO4J_USERNAME"},
            "password": {"env": "NEO4J_PASSWORD"},
            "address": {"env": "NEO4J_ADDRESS"},
            "port": {"env": "NEO4J_PORT"},
            "database": {"env": "NEO4J_DATABASE"},
        }


class BrokerSettings(BaseSettings):
    enable: bool = False
    username: str = "guest"
    password: str = "guest"
    address: str = "localhost"
    namespace: str = "infrahub"

    class Config:
        """Additional parameters to automatically map environment variable to some settings."""

        fields = {
            "username": {"env": "INFRAHUB_BROKER_USERNAME"},
            "password": {"env": "INFRAHUB_BROKER_PASSWORD"},
            "address": {"env": "INFRAHUB_BROKER_ADDRESS"},
            "namespace": {"env": "INFRAHUB_BROKER_NAMESPACE"},
        }


class Settings(BaseSettings):
    """Main Settings Class for the project."""

    main: MainSettings = MainSettings()
    database: DatabaseSettings = DatabaseSettings()
    broker: BrokerSettings = BrokerSettings()


def load(config_file_name="infrahub.toml", config_data=None):
    """Load configuration.

    Configuration is loaded from a config file in toml format that contains the settings,
    or from a dictionary of those settings passed in as "config_data"
    """
    global SETTINGS

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
