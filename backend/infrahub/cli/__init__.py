import typer
from infrahub_sdk.async_typer import AsyncTyper

from infrahub import config
from infrahub.core.initialization import initialization

from ..workers.dependencies import get_database
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

    db = await get_database()

    async with db.start_session() as db:
        await initialization(db=db)


@app.command()
def shell() -> None:
    """Start a python shell within Infrahub context (requires IPython)."""
    from infrahub_sdk import InfrahubClient
    from IPython import start_ipython
    from traitlets.config import Config

    from infrahub import config
    from infrahub.components import ComponentType
    from infrahub.core.branch import Branch
    from infrahub.core.initialization import initialization
    from infrahub.core.manager import NodeManager
    from infrahub.core.registry import registry
    from infrahub.dependencies.registry import build_component_registry
    from infrahub.lock import initialize_lock
    from infrahub.services import InfrahubServices
    from infrahub.workers.dependencies import (
        get_cache,
        get_component,
        get_database,
        get_workflow,
        set_component_type,
    )

    async def initialize_service() -> InfrahubServices:
        config.load_and_exit()
        client = InfrahubClient()

        component_type = ComponentType.GIT_AGENT
        set_component_type(component_type=component_type)

        database = await get_database()

        build_component_registry()

        workflow = get_workflow()
        cache = await get_cache()
        component = await get_component()
        service = await InfrahubServices.new(
            cache=cache,
            client=client,
            database=database,
            workflow=workflow,
            component=component,
            component_type=component_type,
        )
        initialize_lock(service=service)

        async with service.database as db:
            await initialization(db=db)
        await service.component.refresh_schema_hash()

        return service

    def welcome() -> None:
        print("--------------------------------------")
        print("infrahub interactive shell initialized")
        print("--------------------------------------")
        print("Available objects:")
        print("* db: InfrahubDatabase")
        print("* Branch: Branch")
        print("* NodeManager: NodeManager")
        print("* registry: Registry")
        print("* service: InfrahubServices")
        print()
        print("Example use:")
        print("In [1] tags = await NodeManager.query(schema='BuiltinTag', db=db)")

    c = Config()
    c.InteractiveShellApp.exec_lines = [
        "service = await initialize_service()",
        "db = service.database",
        "welcome()",
    ]
    c.TerminalInteractiveShell.colors = "Neutral"

    user_ns = {
        "initialize_service": initialize_service,
        "welcome": welcome,
        "NodeManager": NodeManager,
        "Branch": Branch,
        "registry": registry,
    }

    start_ipython(argv=[], config=c, user_ns=user_ns)
