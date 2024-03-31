from rich.console import Console

from ..schema import InfrahubRepositoryConfig


def list_jinja2_transforms(config: InfrahubRepositoryConfig) -> None:
    console = Console()
    console.print(f"Jinja2 transforms defined in repository: {len(config.jinja2_transforms)}")

    for transform in config.jinja2_transforms:
        console.print(f"{transform.name} ({transform.template_path})")
