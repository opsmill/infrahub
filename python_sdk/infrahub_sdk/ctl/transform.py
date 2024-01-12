import importlib
from pathlib import Path
from typing import Optional

from rich.console import Console

from ..schema import InfrahubPythonTransformConfig, InfrahubRepositoryConfig
from ..transforms import InfrahubTransform
from .exceptions import InfrahubTransformNotFoundError


def list_transforms(config: InfrahubRepositoryConfig) -> None:
    console = Console()
    console.print(f"Python transforms defined in repository: {len(config.python_transforms)}")

    for transform in config.python_transforms:
        console.print(f"{transform.name} ({transform.file_path}::{transform.class_name})")


def get_transform_class_instance(
    transform_config: InfrahubPythonTransformConfig,
    search_path: Optional[Path] = None,
) -> InfrahubTransform:
    if transform_config.file_path.is_absolute() or search_path is None:
        search_location = transform_config.file_path
    else:
        search_location = search_path / transform_config.file_path

    try:
        spec = importlib.util.spec_from_file_location(transform_config.class_name, search_location)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get the specified class from the module
        transform_class = getattr(module, transform_config.class_name)

        # Create an instance of the class
        transform_instance = transform_class()
    except (FileNotFoundError, AttributeError) as exc:
        raise InfrahubTransformNotFoundError(name=transform_config.name) from exc

    return transform_instance
