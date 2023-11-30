import asyncio
import functools
import importlib
import json
import linecache
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import jinja2
import typer

from infrahub_sdk.transfer.export.interface import ExporterInterface
from infrahub_sdk.transfer.export.json import JSONExporter

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from rich.console import Console
from rich.logging import RichHandler
from rich.syntax import Syntax
from rich.traceback import Frame, Traceback

import infrahub_ctl.config as config
from infrahub_ctl.branch import app as branch_app
from infrahub_ctl.check import app as check_app
from infrahub_ctl.client import initialize_client
from infrahub_ctl.exceptions import InfrahubTransformNotFoundError, QueryNotFoundError
from infrahub_ctl.repository import get_repository_config
from infrahub_ctl.schema import app as schema
from infrahub_ctl.transform import list_transforms
from infrahub_ctl.utils import (
    execute_graphql_query,
    parse_cli_vars,
)
from infrahub_ctl.validate import app as validate_app
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.schema import InfrahubPythonTransformConfig, InfrahubRepositoryConfig, InfrahubRepositoryRFileConfig
from infrahub_sdk.transforms import InfrahubTransform
from infrahub_sdk.utils import get_branch

app = typer.Typer(pretty_exceptions_show_locals=False)

app.add_typer(branch_app, name="branch")
app.add_typer(check_app, name="check")
app.add_typer(schema, name="schema")
app.add_typer(validate_app, name="validate")

console = Console()


async def _run(
    script: Path,
    method: str,
    log: logging.Logger,
    branch: str,
    concurrent: int,
    timeout: int,
) -> None:
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

    client = await initialize_client(timeout=timeout, max_concurrent_execution=concurrent)

    func = getattr(module, method)
    await func(client=client, log=log, branch=branch)


def identify_faulty_jinja_code(traceback: Traceback, nbr_context_lines: int = 3) -> List[Tuple[Frame, Syntax]]:
    response = []

    # The Traceback from rich is very helpfull to parse the entire stack trace
    # to will generate a Frame object for each exception in the trace

    # Extract only the Jinja related exceptioin from the stack
    frames = [frame for frame in traceback.trace.stacks[0].frames if frame.filename.endswith(".j2")]

    for frame in frames:
        code = "".join(linecache.getlines(frame.filename))
        lexer_name = Traceback._guess_lexer(frame.filename, code)
        syntax = Syntax(
            code,
            lexer_name,
            line_numbers=True,
            line_range=(
                frame.lineno - nbr_context_lines,
                frame.lineno + nbr_context_lines,
            ),
            highlight_lines={frame.lineno},
            code_width=88,
            theme=traceback.theme,
            dedent=False,
        )
        response.append((frame, syntax))

    return response


def get_transform_class_instance(transform_config: InfrahubPythonTransformConfig) -> InfrahubTransform:
    try:
        spec = importlib.util.spec_from_file_location(transform_config.class_name, transform_config.file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get the specified class from the module
        transform_class = getattr(module, transform_config.class_name)

        # Create an instance of the class
        transform_instance = transform_class()
    except (FileNotFoundError, AttributeError) as exc:
        raise InfrahubTransformNotFoundError(name=transform_config.name) from exc

    return transform_instance


def render_jinja2_template(template_path: Path, variables: Dict[str, str], data: str) -> str:
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


def find_rfile_in_repository_config(
    rfile: str, repository_config: InfrahubRepositoryConfig
) -> InfrahubRepositoryRFileConfig:
    filtered = [entry for entry in repository_config.rfiles if entry.name == rfile]
    if len(filtered) == 0 or len(filtered) > 1:
        raise ValueError
    return filtered[0]


def _run_transform(query: str, variables: Dict[str, Any], transformer: Callable, branch: str, debug: bool):
    branch = get_branch(branch)

    try:
        response = execute_graphql_query(query, variables, branch, debug)
    except QueryNotFoundError as exc:
        console.print(f"[red]Unable to find query : {exc}")
        raise typer.Exit(1) from exc
    except GraphQLError as exc:
        console.print(f"[red]{len(exc.errors)} error(s) occured while executing the query")
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
    rfile_name: str,
    variables: Optional[List[str]] = typer.Argument(
        None, help="Variables to pass along with the query. Format key=value key=value."
    ),
    branch: str = typer.Option(None, help="Branch on which to render the RFile."),
    debug: bool = False,
    config_file: str = typer.Option(config.DEFAULT_CONFIG_FILE, envvar=config.ENVVAR_CONFIG_FILE),
) -> None:
    """Render a local Jinja Template (RFile) for debugging purpose."""

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    variables_dict = parse_cli_vars(variables)
    repository_config = get_repository_config(Path(config.INFRAHUB_REPO_CONFIG_FILE))

    try:
        rfile = find_rfile_in_repository_config(rfile_name, repository_config)
    except ValueError as exc:
        console.print(f"[red]Unable to find {rfile_name} in {config.INFRAHUB_REPO_CONFIG_FILE}")
        raise typer.Exit(1) from exc

    transformer = functools.partial(render_jinja2_template, rfile.template_path, variables_dict)
    result = _run_transform(rfile.query, variables_dict, transformer, branch, debug)
    console.print(result)


@app.command(name="transform")
def transform(
    transform_name: str = typer.Argument("Name of the Python transformation class"),
    variables: Optional[List[str]] = typer.Argument(
        None, help="Variables to pass along with the query. Format key=value key=value."
    ),
    branch: str = typer.Option(None, help="Branch on which to run the transformation"),
    debug: bool = False,
    config_file: str = typer.Option(config.DEFAULT_CONFIG_FILE, envvar=config.ENVVAR_CONFIG_FILE),
    list_available: bool = typer.Option(False, "--list", help="Show available transforms"),
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
    console.print(json.dumps(result, indent=2))


@app.command(name="run")
def run(
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

    asyncio.run(
        _run(
            script=script,
            method=method,
            log=log,
            branch=branch,
            concurrent=concurrent,
            timeout=timeout,
        )
    )


@app.command(name="export")
def export(
    config_file: str = typer.Option("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
    branch: str = typer.Option("main", help="Branch from which to export"),
    concurrent: int = typer.Option(
        4,
        help="Maximum number of requests to execute at the same time.",
        envvar="INFRAHUBCTL_CONCURRENT_EXECUTION",
    ),
    timeout: int = typer.Option(60, help="Timeout in sec", envvar="INFRAHUBCTL_TIMEOUT"),
) -> None:
    """Export node(s)."""
    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)
    exporter = JSONExporter()
    exported = aiorun(
        _export(
            exporter,
            branch=branch,
            concurrent=concurrent,
            timeout=timeout,
        )
    )
    console = Console()
    console.print(exported)


async def _export(exporter: ExporterInterface, branch: str, concurrent: int, timeout: int) -> str:
    client = await initialize_client(timeout=timeout, max_concurrent_execution=concurrent)
    accounts = await client.all("CoreAccount", branch=branch)
    return await exporter.export(accounts)
