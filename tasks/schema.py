from pathlib import Path

from invoke.context import Context
from invoke.tasks import task

from .utils import REPO_BASE

SDK_DIRECTORY = f"{REPO_BASE}/generated/python-sdk"
INFRAHUB_DIRECTORY = f"{REPO_BASE}/generated/python-sdk"


@task
def generate_jsonschema(context: Context):
    """Generate JSON schemas into ./generated"""

    generate_sdk_repository_config()


def generate_sdk_repository_config():
    from infrahub_sdk.schema import InfrahubRepositoryConfig

    repository_dir = f"{SDK_DIRECTORY}/repository-config"
    Path(repository_dir).mkdir(parents=True, exist_ok=True)
    schema = InfrahubRepositoryConfig.schema_json(indent=4)

    write(filename=f"{repository_dir}/develop.json", content=schema)


def write(filename: str, content: str) -> None:
    with open(filename, "w", encoding="utf-8") as fobj:
        fobj.write(content)
    print(f"Wrote to {filename}")
