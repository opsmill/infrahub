"""Config Clas."""
import os
import os.path
import sys
from pathlib import Path

import toml
from pydantic import BaseSettings, ValidationError

SETTINGS = None


class Settings(BaseSettings):
    """Main Settings Class for the project."""

    server_address: str = "http://localhost:8000"
    api_key: str


def load(config_file_name="infrahubctl.toml", config_data=None):
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


def load_and_exit(config_file_name="infrahubctl.toml", config_data=None):
    """Calls load, but wraps it in a try except block.

    This is done to handle a ValidationErorr which is raised when settings are specified but invalid.
    In such cases, a message is printed to the screen indicating the settings which don't pass validation.

    Args:
        config_file_name (str, optional): [description]. Defaults to "pyprojectctl.toml".
        config_data (dict, optional): [description]. Defaults to None.
    """
    try:
        load(config_file_name=config_file_name, config_data=config_data)
    except ValidationError as err:
        print(f"Configuration not valid, found {len(err.errors())} error(s)")
        for error in err.errors():
            print(f"  {'/'.join(error['loc'])} | {error['msg']} ({error['type']})")
        sys.exit(1)
