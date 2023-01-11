import glob
import logging
import os
import sys
from asyncio import run as aiorun
from typing import List, Optional

import httpx
import jinja2
import typer
import yaml
from git import Repo
from rich.logging import RichHandler

import infrahub.config as config
from infrahub.cli.check import app as check_app
from infrahub.cli.db import app as db_app
from infrahub.cli.events import app as events_app
from infrahub.cli.git_agent import app as git_app
from infrahub.cli.server import app as server_app
from infrahub.cli.test import app as test_app
from infrahub.core.initialization import initialization
from infrahub.database import get_db

app = typer.Typer()

app.add_typer(server_app, name="server", help="Control the API Server.")
app.add_typer(git_app, name="git-agent", help="Control the GIT Repositories.")
app.add_typer(db_app, name="db", help="Manage the database.")
app.add_typer(test_app, name="test", help="Execute unit and integration tests.")
app.add_typer(check_app, name="check", help="Execute Integration checks.")
app.add_typer(events_app, name="events", help="Interact with the events system.")


def execute_query(
    query,
    server: str = "http://localhost",
    variables: dict = None,
    branch: str = "main",
    rebase: bool = False,
    at=None,
    timeout: int = 10,
    params: dict = None,
):
    """Execute a GraphQL Query via the GraphQL API endpoint."""
    payload = {"query": query, "variables": variables}
    params = params if params else {}

    if at and "at" not in params:
        params["at"] = at
    if "rebase" not in params:
        params["rebase"] = str(rebase)

    response = httpx.post(f"{server}/graphql/{branch}", json=payload, timeout=timeout, params=params)
    response.raise_for_status()
    return response.json()


def find_graphql_query(name, directory="."):

    for query_file in glob.glob(f"{directory}/**/*.gql", recursive=True):
        filename = os.path.basename(query_file)
        query_name = os.path.splitext(filename)[0]
        if query_name != name:
            continue
        with open(query_file, "r") as file_data:
            query_string = file_data.read()

        return query_string

    return None


async def _init_shell(config_file: str):
    """Launch a Python Interactive shell."""
    config.load_and_exit(config_file_name=config_file)

    db = await get_db()

    async with db.session(database=config.SETTINGS.database.database) as session:
        await initialization(session=session)


@app.command()
def shell(config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG")):
    aiorun(_init_shell(config_file=config_file))

    # TODO add check to properly exit of ipython is not installed
    from IPython import embed
    from rich import pretty
    from traitlets.config import get_config

    pretty.install()

    c = get_config()
    c.InteractiveShellEmbed.colors = "Linux"
    c.InteractiveShellApp.extensions.append("rich")
    embed(config=c)


@app.command()
def render(
    rfile: str,
    params: Optional[List[str]] = typer.Argument(None),
    server: str = "http://localhost:8000",
    branch: str = "main",
    debug: bool = False,
):
    """Render a local Jinja Template (RFile) for debugging purpose."""
    log_level = "DEBUG" if debug else "INFO"

    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahub")

    if not branch:
        repo = Repo(".")
        branch = str(repo.active_branch)

    INFRAHUB_CONFIG_FILE = ".infrahub.yml"

    if not os.path.exists(INFRAHUB_CONFIG_FILE):
        log.error("unable to locate the file '{INFRAHUB_CONFIG_FILE}'")
        sys.exit(1)

    with open(INFRAHUB_CONFIG_FILE, "r") as file_data:
        yaml_data = file_data.read()

    try:
        data = yaml.safe_load(yaml_data)
    except yaml.YAMLError as exc:
        log.error(f"Unable to load YAML file {INFRAHUB_CONFIG_FILE} : {exc.message}")
        sys.exit(1)

    if "rfiles" not in data or rfile not in data.get("rfiles", {}):
        log.error(f"Unable to find {rfile} in {INFRAHUB_CONFIG_FILE}")
        exit(1)

    rfile_data = data["rfiles"][rfile]

    query = find_graphql_query(rfile_data.get("query"))

    params = {item.split("=")[0]: item.split("=")[1] for item in params}
    response = execute_query(server=server, query=query, variables=params, branch=branch)

    template_path = rfile_data.get("template_path")
    if not os.path.isfile(rfile_data.get("template_path")):
        log.error(f"Unable to locate the template at {template_path}")

    templateLoader = jinja2.FileSystemLoader(searchpath=".")
    templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)
    template = templateEnv.get_template(template_path)

    print(template.render(**params, **response))
