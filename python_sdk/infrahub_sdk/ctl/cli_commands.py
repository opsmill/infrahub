import asyncio
import functools
import importlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import jinja2
import typer
from httpx import HTTPError
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import Traceback

from infrahub_sdk import __version__ as sdk_version
from infrahub_sdk.async_typer import AsyncTyper
from infrahub_sdk.ctl import config
from infrahub_sdk.ctl.branch import app as branch_app
from infrahub_sdk.ctl.check import run as run_check
from infrahub_sdk.ctl.client import initialize_client, initialize_client_sync
from infrahub_sdk.ctl.exceptions import QueryNotFoundError
from infrahub_sdk.ctl.repository import get_repository_config
from infrahub_sdk.ctl.schema import app as schema
from infrahub_sdk.ctl.transform import list_transforms
from infrahub_sdk.ctl.utils import execute_graphql_query, parse_cli_vars
from infrahub_sdk.ctl.validate import app as validate_app
from infrahub_sdk.exceptions import (
    AuthenticationError,
    GraphQLError,
    InfrahubTransformNotFoundError,
    ServerNotReachableError,
    ServerNotResponsiveError,
)
from infrahub_sdk.transforms import get_transform_class_instance
from infrahub_sdk.utils import get_branch, identify_faulty_jinja_code, write_to_file

from .exporter import dump
from .importer import load

app = AsyncTyper(pretty_exceptions_show_locals=False)

app.add_typer(branch_app, name="branch")
app.add_typer(schema, name="schema")
app.add_typer(validate_app, name="validate")
app.command(name="dump")(dump)
app.command(name="load")(load)

console = Console()


@app.command(name="check")
def check(
    check_name: str = typer.Argument(default="", help="Name of the Python check"),
    branch: Optional[str] = None,
    path: str = typer.Option(".", help="Root directory"),
    debug: bool = False,
    format_json: bool = False,
    config_file: str = typer.Option(config.DEFAULT_CONFIG_FILE, envvar=config.ENVVAR_CONFIG_FILE),
    list_available: bool = typer.Option(False, "--list", help="Show available Python checks"),
    variables: Optional[List[str]] = typer.Argument(
        None, help="Variables to pass along with the query. Format key=value key=value."
    ),
) -> None:
    """Execute user-defined checks."""

    variables_dict = parse_cli_vars(variables)
    run_check(
        path=path,
        debug=debug,
        branch=branch,
        format_json=format_json,
        config_file=config_file,
        list_available=list_available,
        name=check_name,
        variables=variables_dict,
    )


@app.command(name="run")
async def run(
    script: Path,
    method: str = "run",
    debug: bool = False,
    config_file: str = typer.Option("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
    branch: str = typer.Option("main", help="Branch on which to run the script."),
    concurrent: int = typer.Option(
        4,
        help="Maximum number of requests to execute at the same time.",
        envvar="INFRAHUBCTL_CONCURRENT_EXECUTION",
    ),
    timeout: int = typer.Option(60, help="Timeout in sec", envvar="INFRAHUBCTL_TIMEOUT"),
    variables: Optional[List[str]] = typer.Argument(
        None, help="Variables to pass along with the query. Format key=value key=value."
    ),
) -> None:
    """Execute a script."""

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)

    log_level = "DEBUG" if debug else "INFO"
    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahubctl")

    variables_dict = parse_cli_vars(variables)

    directory_name = os.path.dirname(script)
    filename = os.path.basename(script)
    module_name = os.path.splitext(filename)[0]

    if directory_name not in sys.path:
        sys.path.append(directory_name)

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise typer.Abort(f"Unable to Load the Python script at {script}") from exc

    if not hasattr(module, method):
        raise typer.Abort(f"Unable to Load the method {method} in the Python script at {script}")

    client = await initialize_client(
        branch=branch, timeout=timeout, max_concurrent_execution=concurrent, identifier=module_name
    )
    func = getattr(module, method)
    await func(client=client, log=log, branch=branch, **variables_dict)


def render_jinja2_template(template_path: Path, variables: Dict[str, str], data: Dict[str, Any]) -> str:
    if not template_path.is_file():
        console.print(f"[red]Unable to locate the template at {template_path}")
        raise typer.Exit(1)

    templateLoader = jinja2.FileSystemLoader(searchpath=".")
    templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)
    template = templateEnv.get_template(str(template_path))

    try:
        rendered_tpl = template.render(**variables, data=data)  # type: ignore[arg-type]
    except jinja2.TemplateSyntaxError as exc:
        console.print("[red]Syntax Error detected on the template")
        console.print(f"[yellow]  {exc}")
        raise typer.Exit(1) from exc

    except jinja2.UndefinedError as exc:
        console.print("[red]An error occured while rendering the jinja template")
        traceback = Traceback(show_locals=False)
        errors = identify_faulty_jinja_code(traceback=traceback)
        for frame, syntax in errors:
            console.print(f"[yellow]{frame.filename} on line {frame.lineno}\n")
            console.print(syntax)
        console.print("")
        console.print(traceback.trace.stacks[0].exc_value)
        raise typer.Exit(1) from exc

    return rendered_tpl


def _run_transform(query: str, variables: Dict[str, Any], transformer: Callable, branch: str, debug: bool):
    branch = get_branch(branch)

    try:
        response = execute_graphql_query(query, variables, branch, debug)
    except QueryNotFoundError as exc:
        console.print(f"[red]Unable to find query : {exc}")
        raise typer.Exit(1) from exc
    except GraphQLError as exc:
        console.print(f"[red]{len(exc.errors)} error(s) occurred while executing the query")
        for error in exc.errors:
            if isinstance(error, dict) and "message" in error and "locations" in error:
                console.print(f"[yellow] - Message: {error['message']}")  # type: ignore[typeddict-item]
                console.print(f"[yellow]   Location: {error['locations']}")  # type: ignore[typeddict-item]
            elif isinstance(error, str) and "Branch:" in error:
                console.print(f"[yellow] - {error}")
                console.print("[yellow]   you can specify a different branch with --branch")
        raise typer.Abort()

    if asyncio.iscoroutinefunction(transformer.func):
        output = asyncio.run(transformer(response))
    else:
        output = transformer(response)
    return output


@app.command(name="render")
def render(
    transform_name: str,
    variables: Optional[List[str]] = typer.Argument(
        None, help="Variables to pass along with the query. Format key=value key=value."
    ),
    branch: str = typer.Option(None, help="Branch on which to render the transform."),
    debug: bool = False,
    config_file: str = typer.Option(config.DEFAULT_CONFIG_FILE, envvar=config.ENVVAR_CONFIG_FILE),
    out: str = typer.Option(None, help="Path to a file to save the result."),
) -> None:
    """Render a local Jinja2 Transform for debugging purpose."""

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    variables_dict = parse_cli_vars(variables)
    repository_config = get_repository_config(Path(config.INFRAHUB_REPO_CONFIG_FILE))

    try:
        transform_config = repository_config.get_jinja2_transform(name=transform_name)
    except KeyError as exc:
        console.print(f"[red]Unable to find {transform_name} in {config.INFRAHUB_REPO_CONFIG_FILE}")
        raise typer.Exit(1) from exc

    transformer = functools.partial(render_jinja2_template, transform_config.template_path, variables_dict)
    result = _run_transform(transform_config.query, variables_dict, transformer, branch, debug)

    if out:
        write_to_file(Path(out), result)
    else:
        console.print(result)


@app.command(name="transform")
def transform(
    transform_name: str = typer.Argument(default="", help="Name of the Python transformation", show_default=False),
    variables: Optional[List[str]] = typer.Argument(
        None, help="Variables to pass along with the query. Format key=value key=value."
    ),
    branch: str = typer.Option(None, help="Branch on which to run the transformation"),
    debug: bool = False,
    config_file: str = typer.Option(config.DEFAULT_CONFIG_FILE, envvar=config.ENVVAR_CONFIG_FILE),
    list_available: bool = typer.Option(False, "--list", help="Show available transforms"),
    out: str = typer.Option(None, help="Path to a file to save the result."),
) -> None:
    """Render a local transform (TransformPython) for debugging purpose."""

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    variables_dict = parse_cli_vars(variables)
    repository_config = get_repository_config(Path(config.INFRAHUB_REPO_CONFIG_FILE))

    if list_available:
        list_transforms(config=repository_config)
        return

    matched = [transform for transform in repository_config.python_transforms if transform.name == transform_name]

    if not matched:
        console.print(f"[red]Unable to find requested transform: {transform_name}")
        list_transforms(config=repository_config)
        return

    transform_config = matched[0]

    try:
        transform_instance = get_transform_class_instance(transform_config=transform_config)
    except InfrahubTransformNotFoundError as exc:
        console.print(f"Unable to load {transform_name} from python_transforms")
        raise typer.Exit(1) from exc

    transformer = functools.partial(transform_instance.transform)
    result = _run_transform(
        query=transform_instance.query, variables=variables_dict, transformer=transformer, branch=branch, debug=debug
    )

    json_string = json.dumps(result, indent=2, sort_keys=True)
    if out:
        write_to_file(Path(out), json_string)
    else:
        console.print(json_string)


@app.command(name="version")
def version(config_file: str = typer.Option(config.DEFAULT_CONFIG_FILE, envvar=config.ENVVAR_CONFIG_FILE)):
    """Display the version of Infrahub and the version of the Python SDK in use."""
    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)
    client = initialize_client_sync()

    query = "query { InfrahubInfo { version }}"
    try:
        response = client.execute_graphql(query=query, raise_for_error=True)
    except (AuthenticationError, GraphQLError, HTTPError, ServerNotReachableError, ServerNotResponsiveError) as exc:
        console.print("Unable to gather infrahub version")
        raise typer.Exit(1) from exc

    infrahub_version = response["InfrahubInfo"]["version"]
    console.print(f"Infrahub: v{infrahub_version}\nSDK: v{sdk_version}")
