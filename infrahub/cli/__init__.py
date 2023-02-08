from asyncio import run as aiorun

import typer

import infrahub.config as config
from infrahub.cli.db import app as db_app
from infrahub.cli.events import app as events_app
from infrahub.cli.git_agent import app as git_app
from infrahub.cli.server import app as server_app
from infrahub.cli.test import app as test_app
from infrahub.core.initialization import initialization
from infrahub.database import get_db

# pylint: disable=import-outside-toplevel

app = typer.Typer()

app.add_typer(server_app, name="server", help="Control the API Server.")
app.add_typer(git_app, name="git-agent", help="Control the GIT Repositories.")
app.add_typer(db_app, name="db", help="Manage the database.")
app.add_typer(test_app, name="test", help="Execute unit and integration tests.")
app.add_typer(events_app, name="events", help="Interact with the events system.")


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
