import importlib
import logging
import os
import sys
from asyncio import run as aiorun
from pathlib import Path
from typing import List, Optional

import jinja2
import typer
import yaml
from git import Repo
from rich.logging import RichHandler

# pylint: disable=import-outside-toplevel
import infrahub_ctl.config as config
from infrahub_client import InfrahubClient
from infrahub_ctl.branch import app as branch_app
from infrahub_ctl.check import app as check_app
from infrahub_ctl.exceptions import QueryNotFoundError
from infrahub_ctl.schema import app as schema
from infrahub_ctl.utils import execute_query, find_graphql_query
from infrahub_ctl.validate import app as validate_app

app = typer.Typer()

app.add_typer(branch_app, name="branch")
app.add_typer(check_app, name="check")
app.add_typer(schema, name="schema")
app.add_typer(validate_app, name="validate")


async def _render(
    rfile: str,
    params: Optional[List[str]],
    config_file: str,
    branch: str,
    debug: bool,
) -> None:
    """Render a local Jinja Template (RFile) for debugging purpose."""
    log_level = "DEBUG" if debug else "INFO"

    config.load_and_exit(config_file=config_file)

    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahubctl")

    if not branch:
        repo = Repo(".")
        branch = str(repo.active_branch)

    INFRAHUB_CONFIG_FILE = ".infrahub.yml"

    if not os.path.exists(INFRAHUB_CONFIG_FILE):
        log.error("unable to locate the file '{INFRAHUB_CONFIG_FILE}'")
        sys.exit(1)

    with open(INFRAHUB_CONFIG_FILE, "r", encoding="UTF-8") as file_data:
        yaml_data = file_data.read()

    try:
        data = yaml.safe_load(yaml_data)
    except yaml.YAMLError as exc:
        log.error(f"Unable to load YAML file {INFRAHUB_CONFIG_FILE} : {exc}")
        sys.exit(1)

    if "rfiles" not in data or rfile not in data.get("rfiles", {}):
        log.error(f"Unable to find {rfile} in {INFRAHUB_CONFIG_FILE}")
        sys.exit(1)

    rfile_data = data["rfiles"][rfile]

    try:
        query = find_graphql_query(rfile_data.get("query"))
    except QueryNotFoundError as exc:
        log.error(f"Unable to find query : {exc}")
        sys.exit(1)

    params_dict: dict = {item.split("=")[0]: item.split("=")[1] for item in params} if params else {}

    response = execute_query(server=config.SETTINGS.server_address, query=query, variables=params_dict, branch=branch)

    template_path = rfile_data.get("template_path")
    if not os.path.isfile(rfile_data.get("template_path")):
        log.error(f"Unable to locate the template at {template_path}")

    templateLoader = jinja2.FileSystemLoader(searchpath=".")
    templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)
    template = templateEnv.get_template(template_path)

    print(template.render(**params_dict, **response))


async def _run(
    script: Path,
    method: str,
    log: logging.Logger,
    branch: str,
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

    client = await InfrahubClient.init(address=config.SETTINGS.server_address, insert_tracker=True)
    func = getattr(module, method)
    await func(client=client, log=log, branch=branch)


@app.command()
def render(
    rfile: str,
    params: Optional[List[str]] = typer.Argument(None),
    branch: str = "main",
    debug: bool = False,
    config_file: str = typer.Option("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
) -> None:
    """Render a local Jinja Template (RFile) for debugging purpose."""
    aiorun(_render(rfile=rfile, params=params, config_file=config_file, branch=branch, debug=debug))


@app.command()
def run(
    script: Path,
    method: str = "run",
    debug: bool = False,
    config_file: str = typer.Option("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
    branch: str = typer.Option("main"),
) -> None:
    """Execute a script."""
    config.load_and_exit(config_file=config_file)

    logging.getLogger("infrahub_client").setLevel(logging.CRITICAL)

    log_level = "DEBUG" if debug else "INFO"
    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahubctl")

    aiorun(_run(script=script, method=method, log=log, branch=branch))
