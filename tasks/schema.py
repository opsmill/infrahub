import json
from pathlib import Path

from invoke.context import Context
from invoke.tasks import task

from .utils import REPO_BASE

SDK_DIRECTORY = f"{REPO_BASE}/generated/python-sdk"
INFRAHUB_DIRECTORY = f"{REPO_BASE}/generated/infrahub"


@task
def generate_jsonschema(context: Context):
    """Generate JSON schemas into ./generated"""

    generate_sdk_repository_config()
    generate_infrahub_node_schema()


def generate_infrahub_node_schema():
    from infrahub.api.schema import SchemaLoadAPI

    schema_dir = Path(f"{INFRAHUB_DIRECTORY}/schema")
    schema_dir.mkdir(parents=True, exist_ok=True)

    schema = SchemaLoadAPI.model_json_schema()

    schema["title"] = "InfrahubSchema"

    content = json.dumps(schema, indent=4)

    write(file_path=schema_dir / "develop.json", content=content)


def generate_sdk_repository_config():
    from infrahub_sdk.schema import InfrahubRepositoryConfig

    repository_dir = Path(f"{SDK_DIRECTORY}/repository-config")
    repository_dir.mkdir(parents=True, exist_ok=True)
    schema = json.dumps(InfrahubRepositoryConfig.model_json_schema(), indent=4)

    write(file_path=repository_dir / "develop.json", content=schema)


def write(file_path: Path, content: str) -> None:
    file_path.write_text(content, encoding="utf-8")
    print(f"Wrote to {file_path}")
