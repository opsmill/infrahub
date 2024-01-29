from pathlib import Path

import yaml

from infrahub_sdk.schema import InfrahubRepositoryConfig

from .exceptions import FileNotValidError


def load_repository_config(repo_config_file: Path) -> InfrahubRepositoryConfig:
    if not repo_config_file.is_file():
        raise FileNotFoundError(repo_config_file)

    try:
        yaml_data = repo_config_file.read_text()
        data = yaml.safe_load(yaml_data)
    except yaml.YAMLError as exc:
        raise FileNotValidError(name=str(repo_config_file)) from exc

    return InfrahubRepositoryConfig(**data)
