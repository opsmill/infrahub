import logging
import time
from asyncio import run as aiorun
from pathlib import Path
from typing import List, Optional

import typer
import yaml

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from rich.console import Console
from rich.logging import RichHandler

import infrahub_ctl.config as config
from infrahub_ctl.client import initialize_client
from infrahub_sdk.utils import find_files

app = typer.Typer()


@app.callback()
def callback() -> None:
    """
    Manage the schema in a remote Infrahub instance.
    """


class SchemaFile(pydantic.BaseModel):
    location: Path
    content: Optional[dict] = None
    valid: bool = True
    error_message: Optional[str] = None

    def load_content(self) -> None:
        try:
            self.content = yaml.safe_load(self.location.read_text())
        except yaml.YAMLError:
            self.error_message = "Invalid YAML/JSON file"
            self.valid = False


async def _load(schemas: List[Path], branch: str, log: logging.Logger) -> None:  # pylint: disable=unused-argument
    # pylint: disable=too-many-branches
    console = Console()

    schemas_data: List[SchemaFile] = []
    has_error = False

    for schema in schemas:
        if schema.is_file():
            schema_file = SchemaFile(location=schema)
            schema_file.load_content()
            schemas_data.append(schema_file)
        elif schema.is_dir():
            files = find_files(extension=["yaml", "yml", "json"], directory=schema, recursive=True)
            for item in files:
                schema_file = SchemaFile(location=item)
                schema_file.load_content()
                schemas_data.append(schema_file)
        else:
            console.print(f"[red]Schema path: {schema} does not exist!")
            has_error = True

    for schema_file in schemas_data:
        if schema_file.valid:
            continue
        console.print(f"[red]{schema_file.error_message} ({schema_file.location})")
        has_error = True

    if has_error:
        raise typer.Exit(2)

    client = await initialize_client()

    # Valid data format of content
    for schema_file in schemas_data:
        try:
            client.schema.validate(schema_file.content)
        except pydantic.ValidationError as exc:
            console.print(f"[red]Schema not valid, found '{len(exc.errors())}' error(s) in {schema_file.location}")
            has_error = True
            for error in exc.errors():
                loc_str = [str(item) for item in error["loc"]]
                console.print(f"  '{'/'.join(loc_str)}' | {error['msg']} ({error['type']})")

    if has_error:
        raise typer.Exit(2)

    start_time = time.time()
    _, errors = await client.schema.load(schemas=[item.content for item in schemas_data], branch=branch)
    loading_time = time.time() - start_time

    if errors:
        console.print("[red]Unable to load the schema:")
        if "detail" in errors:
            for error in errors.get("detail"):
                loc_str = [str(item) for item in error["loc"][1:]]
                console.print(f"  '{'/'.join(loc_str)}' | {error['msg']} ({error['type']})")
        elif "error" in errors:
            console.print(f"  '{errors.get('error')}'")
        else:
            console.print(f"  '{errors}'")
    else:
        for schema_file in schemas_data:
            console.print(f"[green] schema '{schema_file.location}' loaded successfully in {loading_time:.3f} sec!")


@app.command()
def load(
    schemas: List[Path],
    debug: bool = False,
    branch: str = typer.Option("main", help="Branch on which to load the schema."),
    config_file: str = typer.Option("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
) -> None:
    """Load a schema file into Infrahub."""
    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)

    log_level = "DEBUG" if debug else "INFO"
    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahubctl")

    aiorun(_load(schemas=schemas, branch=branch, log=log))


@app.command()
def migrate() -> None:
    """Migrate the schema to the latest version. (Not Implemented Yet)"""
    print("Not implemented yet.")
