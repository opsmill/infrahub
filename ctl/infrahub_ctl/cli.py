import importlib
import linecache
import logging
import os
import sys
from asyncio import run as aiorun
from pathlib import Path
from typing import List, Optional, Tuple

import jinja2
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.logging import RichHandler
from rich.syntax import Syntax
from rich.traceback import Frame, Traceback

# pylint: disable=import-outside-toplevel
import infrahub_ctl.config as config
from infrahub_client import InfrahubClient, InfrahubClientSync
from infrahub_client.exceptions import GraphQLError
from infrahub_client.schema import InfrahubRepositoryConfig
from infrahub_ctl.branch import app as branch_app
from infrahub_ctl.check import app as check_app
from infrahub_ctl.exceptions import (
    FileNotFoundError,
    FileNotValidError,
    QueryNotFoundError,
)
from infrahub_ctl.schema import app as schema
from infrahub_ctl.utils import (
    find_graphql_query,
    get_branch,
    load_repository_config_file,
    parse_cli_vars,
)
from infrahub_ctl.validate import app as validate_app

app = typer.Typer(pretty_exceptions_show_locals=False)

app.add_typer(branch_app, name="branch")
app.add_typer(check_app, name="check")
app.add_typer(schema, name="schema")
app.add_typer(validate_app, name="validate")


async def _run(script: Path, method: str, log: logging.Logger, branch: str, concurrent: int, timeout: int) -> None:
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

    client = await InfrahubClient.init(
        address=config.SETTINGS.server_address,
        insert_tracker=True,
        max_concurrent_execution=concurrent,
        default_timeout=timeout,
    )
    func = getattr(module, method)
    await func(client=client, log=log, branch=branch)


def identify_faulty_jinja_code(tb, nbr_context_lines: int = 3) -> List[Tuple[Frame, Syntax]]:
    response = []

    # The Traceback from rich is very helpfull to parse the entire stack trace
    # to will generate a Frame object for each exception in the trace

    # Extract only the Jinja related exceptioin from the stack
    frames = [frame for frame in tb.trace.stacks[0].frames if frame.filename.endswith(".j2")]

    for frame in frames:
        code = "".join(linecache.getlines(frame.filename))
        lexer_name = Traceback._guess_lexer(frame.filename, code)
        syntax = Syntax(
            code,
            lexer_name,
            line_numbers=True,
            line_range=(frame.lineno - nbr_context_lines, frame.lineno + nbr_context_lines),
            highlight_lines={frame.lineno},
            code_width=88,
            theme=tb.theme,
            dedent=False,
        )
        response.append((frame, syntax))

    return response


@app.command()
def render(
    rfile: str,
    vars: Optional[List[str]] = typer.Argument(
        None, help="Variables to pass along with the query. Format key=value key=value."
    ),
    branch: str = typer.Option(None, help="Branch on which to rendre the RFile."),
    debug: bool = False,
    config_file: str = typer.Option(config.DEFAULT_CONFIG_FILE, envvar=config.ENVVAR_CONFIG_FILE),
) -> None:
    """Render a local Jinja Template (RFile) for debugging purpose."""

    branch == get_branch(branch)

    console = Console()

    # ------------------------------------------------------------------
    # Read the configuration file
    # ------------------------------------------------------------------
    try:
        config_file_data = load_repository_config_file(repo_config_file=Path(config.INFRAHUB_REPO_CONFIG_FILE))
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}")
        raise typer.Abort()
    except FileNotValidError as exc:
        console.print(f"[red]{exc}")
        raise typer.Abort()

    try:
        data = InfrahubRepositoryConfig(**config_file_data)
    except ValidationError as exc:
        console.print(f"[red]Repository config file not valid, found {len(exc.errors())} error(s)")
        for error in exc.errors():
            loc_str = [str(item) for item in error["loc"]]
            console.print(f"  {'/'.join(loc_str)} | {error['msg']} ({error['type']})")
        raise typer.Abort()

    # ------------------------------------------------------------------
    # Find the GraphQL Query and Retrive its data
    # ------------------------------------------------------------------
    filtered_rfile = [entry for entry in data.rfiles if entry.name == rfile]
    if not filtered_rfile:
        console.print(f"[red]Unable to find {rfile} in {config.INFRAHUB_REPO_CONFIG_FILE}")
        raise typer.Abort()

    rfile_data = filtered_rfile[0]

    try:
        query_str = find_graphql_query(rfile_data.query)
    except QueryNotFoundError as exc:
        console.print(f"[red]Unable to find query : {exc}")
        raise typer.Abort()

    variables = parse_cli_vars(vars)

    client = InfrahubClientSync.init(address=config.SETTINGS.server_address, insert_tracker=True)
    try:
        response = client.execute_graphql(
            query=query_str, branch_name=branch, variables=variables, raise_for_error=False
        )
    except GraphQLError as exc:
        console.print(f"[red]{len(exc.errors)} error(s) occured while executing the query")
        for error in exc.errors:
            if isinstance(error, dict) and "message" in error and "locations" in error:
                console.print(f"[yellow] - Message: {error['message']}")
                console.print(f"[yellow]   Location: {error['locations']}")
            elif isinstance(error, str) and "Branch:" in error:
                console.print(f"[yellow] - {error}")
                console.print(f"[yellow]   you can specify a different branch with --branch")
        raise typer.Abort()

    # ------------------------------------------------------------------
    # Finally, render the template
    # ------------------------------------------------------------------
    template_path = rfile_data.template_path
    if not template_path.is_file():
        console.print(f"[red]Unable to locate the template at {template_path}")
        raise typer.Abort()

    templateLoader = jinja2.FileSystemLoader(searchpath=".")
    templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)
    template = templateEnv.get_template(str(template_path))

    try:
        rendered_tpl = template.render(data=response, **variables)
    except jinja2.TemplateSyntaxError as exc:
        console.print("[red]Syntax Erro detected on the template")
        console.print(f"[yellow]  {exc}")
        raise typer.Abort()

    except jinja2.UndefinedError as exc:
        console.print("[red]An error occured while rendering the jinja template")
        tb = Traceback(show_locals=False)
        errors = identify_faulty_jinja_code(tb=tb)
        for frame, syntax in errors:
            console.print(f"[yellow]{frame.filename} on line {frame.lineno}\n")
            console.print(syntax)
        console.print("")
        console.print(tb.trace.stacks[0].exc_value)
        raise typer.Abort()

    print(rendered_tpl)


@app.command()
def run(
    script: Path,
    method: str = "run",
    debug: bool = False,
    config_file: str = typer.Option("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
    branch: str = typer.Option("main", help="Branch on which to run the script."),
    concurrent: int = typer.Option(
        4, help="Maximum number of requets to execute at the same time.", envvar="INFRAHUBCTL_CONCURRENT_EXECUTION"
    ),
    timeout: int = typer.Option(60, help="Timeout in sec", envvar="INFRAHUBCTL_TIMEOUT"),
) -> None:
    """Execute a script."""
    config.load_and_exit(config_file=config_file)

    logging.getLogger("infrahub_client").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)

    log_level = "DEBUG" if debug else "INFO"
    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahubctl")

    aiorun(_run(script=script, method=method, log=log, branch=branch, concurrent=concurrent, timeout=timeout))
