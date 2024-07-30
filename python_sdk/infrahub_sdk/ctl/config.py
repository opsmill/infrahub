"""Config Class."""

from pathlib import Path
from typing import Optional, Union

import toml
import typer
from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CONFIG_FILE = "infrahubctl.toml"
ENVVAR_CONFIG_FILE = "INFRAHUBCTL_CONFIG"
INFRAHUB_REPO_CONFIG_FILE = ".infrahub.yml"


class Settings(BaseSettings):
    """Main Settings Class for the project."""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_", populate_by_name=True, extra="allow")
    server_address: str = Field(default="http://localhost:8000", validation_alias="infrahub_address")
    api_token: Optional[str] = Field(default=None)
    default_branch: str = Field(default="main")

    @field_validator("server_address")
    @classmethod
    def cleanup_server_address(cls, v: str) -> str:
        return v.rstrip("/")


class ConfiguredSettings:
    def __init__(self) -> None:
        self._settings: Optional[Settings] = None

    @property
    def active(self) -> Settings:
        if self._settings:
            return self._settings

        print("Configuration not properly loaded")
        raise typer.Abort()

    def load(self, config_file: Union[str, Path] = "infrahubctl.toml", config_data: Optional[dict] = None) -> None:
        """Load configuration.

        Configuration is loaded from a config file in toml format that contains the settings,
        or from a dictionary of those settings passed in as "config_data"
        """

        if self._settings:
            return

        if config_data:
            self._settings = Settings(**config_data)
            return

        if not isinstance(config_file, Path):
            config_file = Path(config_file)

        if config_file.is_file():
            config_string = config_file.read_text(encoding="utf-8")
            config_tmp = toml.loads(config_string)

            self._settings = Settings(**config_tmp)
            return

        self._settings = Settings()

    def load_and_exit(
        self, config_file: Union[str, Path] = "infrahubctl.toml", config_data: Optional[dict] = None
    ) -> None:
        """Calls load, but wraps it in a try except block.

        This is done to handle a ValidationErorr which is raised when settings are specified but invalid.
        In such cases, a message is printed to the screen indicating the settings which don't pass validation.

        Args:
            config_file_name (str, optional): [description]. Defaults to "pyprojectctl.toml".
            config_data (dict, optional): [description]. Defaults to None.
        """

        try:
            self.load(config_file=config_file, config_data=config_data)
        except ValidationError as exc:
            print(f"Configuration not valid, found {len(exc.errors())} error(s)")
            for error in exc.errors():
                loc_str = [str(item) for item in error["loc"]]
                print(f"  {'/'.join(loc_str)} | {error['msg']} ({error['type']})")
            raise typer.Abort()


SETTINGS = ConfiguredSettings()
