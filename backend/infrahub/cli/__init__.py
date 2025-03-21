from asyncio import run as aiorun

import typer
from infrahub_sdk.async_typer import AsyncTyper

from infrahub import config
from infrahub.core.initialization import initialization
from infrahub.database import InfrahubDatabase, get_db

from .context import CliContext
from .db import app as db_app
from .events import app as events_app
from .git_agent import app as git_app
from .server import app as server_app
from .tasks import app as tasks_app
from .upgrade import upgrade_cmd

app = AsyncTyper(name="Infrahub CLI", pretty_exceptions_enable=False)


@app.callback()
def common(ctx: typer.Context) -> None:
    """Infrahub CLI"""
    ctx.obj = CliContext()


app.add_typer(server_app, name="server")
app.add_typer(git_app, name="git-agent", hidden=True)
app.add_typer(db_app, name="db")
app.add_typer(events_app, name="events", help="Interact with the events system.", hidden=True)
app.add_typer(tasks_app, name="tasks", hidden=True)
app.command(name="upgrade")(upgrade_cmd)


async def _init_shell(config_file: str) -> None:
    """Launch a Python Interactive shell."""
    config.load_and_exit(config_file_name=config_file)

    db = InfrahubDatabase(driver=await get_db(retry=1))

    async with db.start_session() as db:
        await initialization(db=db)


@app.command()
def shell(config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG")) -> None:
    """Start a python shell within Infrahub context."""
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
