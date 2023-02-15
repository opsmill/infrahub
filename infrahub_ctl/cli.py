import logging
import os
import sys
from asyncio import run as aiorun
from typing import List, Optional

import jinja2
import typer
import yaml
from git import Repo
from rich.logging import RichHandler

# pylint: disable=import-outside-toplevel
import infrahub_ctl.config as config

from .branch import app as branch_app
from .check import app as check_app
from .schema import app as schema
from .utils import execute_query, find_graphql_query
from .validate import app as validate_app

app = typer.Typer()

app.add_typer(branch_app, name="branch", help="Manage all branches.")
app.add_typer(check_app, name="check", help="Execute Integration checks.")
app.add_typer(schema, name="schema", help="Manage the schema.")
app.add_typer(validate_app, name="validate", help="Validate different components.")


async def _render(
    rfile: str,
    params: Optional[List[str]],
    config_file: str,
    branch: str,
    debug: bool,
):
    """Render a local Jinja Template (RFile) for debugging purpose."""
    log_level = "DEBUG" if debug else "INFO"

    config.load_and_exit(config_file_name=config_file)

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

    query = find_graphql_query(rfile_data.get("query"))

    params = {item.split("=")[0]: item.split("=")[1] for item in params}
    response = execute_query(server=config.SETTINGS.server_address, query=query, variables=params, branch=branch)

    template_path = rfile_data.get("template_path")
    if not os.path.isfile(rfile_data.get("template_path")):
        log.error(f"Unable to locate the template at {template_path}")

    templateLoader = jinja2.FileSystemLoader(searchpath=".")
    templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)
    template = templateEnv.get_template(template_path)

    print(template.render(**params, **response))


@app.command()
def render(
    rfile: str,
    params: Optional[List[str]] = typer.Argument(None),
    config_file: str = typer.Argument("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
    branch: str = "main",
    debug: bool = False,
):
    """Render a local Jinja Template (RFile) for debugging purpose."""
    aiorun(_render(rfile=rfile, params=params, config_file=config_file, branch=branch, debug=debug))
