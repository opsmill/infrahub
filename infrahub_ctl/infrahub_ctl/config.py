"""Config Clas."""
from pathlib import Path
from typing import Optional, Union

import toml
import typer
from pydantic import BaseSettings, ValidationError

SETTINGS = None


class Settings(BaseSettings):
    """Main Settings Class for the project."""

    server_address: str = "http://localhost:8000"
    api_key: Optional[str]


def load(config_file: Union[str, Path] = "infrahubctl.toml", config_data: Optional[dict] = None):
    """Load configuration.

    Configuration is loaded from a config file in toml format that contains the settings,
    or from a dictionary of those settings passed in as "config_data"
    """
    global SETTINGS  # pylint: disable=global-statement

    if config_data:
        SETTINGS = Settings(**config_data)
        return

    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    if config_file.is_file():
        config_string = config_file.read_text(encoding="utf-8")
        config_tmp = toml.loads(config_string)

        SETTINGS = Settings(**config_tmp)
        return

    SETTINGS = Settings()


def load_and_exit(config_file: Union[str, Path] = "infrahubctl.toml", config_data: Optional[dict] = None):
    """Calls load, but wraps it in a try except block.

    This is done to handle a ValidationErorr which is raised when settings are specified but invalid.
    In such cases, a message is printed to the screen indicating the settings which don't pass validation.

    Args:
        config_file_name (str, optional): [description]. Defaults to "pyprojectctl.toml".
        config_data (dict, optional): [description]. Defaults to None.
    """
    try:
        load(config_file=config_file, config_data=config_data)
    except ValidationError as exc:
        print(f"Configuration not valid, found {len(exc.errors())} error(s)")
        for error in exc.errors():
            loc_str = [str(item) for item in error["loc"]]
            print(f"  {'/'.join(loc_str)} | {error['msg']} ({error['type']})")
        raise typer.Abort()
