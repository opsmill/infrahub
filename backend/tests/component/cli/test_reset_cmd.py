import asyncio
from pathlib import Path
from unittest.mock import patch

from click.testing import Result
from prefect.server.models.flows import count_flows, create_flow
from prefect.server.schemas.core import Flow
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL, temporary_settings
from typer.testing import CliRunner

from infrahub.cli import app
from infrahub.cli.db_commands.reset import task_manager_database

runner = CliRunner()


def _seed_task_manager_database(path: Path) -> str:
    """Create a SQLite task manager database holding one flow and return its URL."""
    connection_url = f"sqlite+aiosqlite:///{path}"

    async def _seed() -> None:
        with task_manager_database(connection_url=connection_url) as task_db:
            await task_db.create_db()
            async with await task_db.session() as session, session.begin():
                await create_flow(session=session, flow=Flow(name="seeded"))
            engine = await task_db.engine()
            await engine.dispose()

    asyncio.run(_seed())
    return connection_url


def _count_flows(connection_url: str) -> int:
    async def _count() -> int:
        with task_manager_database(connection_url=connection_url) as task_db:
            async with await task_db.session() as session:
                count = await count_flows(session=session)
            engine = await task_db.engine()
            await engine.dispose()
            return count

    return asyncio.run(_count())


class TestResetCommandTaskManagerOnly:
    """Run the command as it runs in the task-manager container: only the Prefect database is configured."""

    def _invoke(self, connection_url: str, args: list[str], user_input: str | None = None) -> Result:
        with (
            patch("infrahub.cli.db.is_graph_database_configured", return_value=False),
            temporary_settings(updates={PREFECT_API_DATABASE_CONNECTION_URL: connection_url}),
        ):
            return runner.invoke(app, ["db", "reset", *args], input=user_input)

    def test_flag_skips_the_prompt(self, tmp_path: Path) -> None:
        connection_url = _seed_task_manager_database(path=tmp_path / "task-manager.db")

        result = self._invoke(connection_url=connection_url, args=["--yes-task-manager"])

        assert result.exit_code == 0, result.output
        assert "Graph database:" in result.output
        assert "not configured here" in result.output
        assert "Task manager database reset" in result.output
        assert _count_flows(connection_url=connection_url) == 0

    def test_accepted_prompt_resets(self, tmp_path: Path) -> None:
        connection_url = _seed_task_manager_database(path=tmp_path / "task-manager.db")

        result = self._invoke(connection_url=connection_url, args=[], user_input="y\n")

        assert result.exit_code == 0, result.output
        assert "Delete all data from the task manager database?" in result.output
        assert _count_flows(connection_url=connection_url) == 0

    def test_declined_prompt_leaves_the_database_alone(self, tmp_path: Path) -> None:
        connection_url = _seed_task_manager_database(path=tmp_path / "task-manager.db")

        result = self._invoke(connection_url=connection_url, args=[], user_input="n\n")

        assert result.exit_code == 1, result.output
        assert "Task manager database: skipped." in result.output
        assert "Nothing was reset." in result.output
        assert _count_flows(connection_url=connection_url) == 1

    def test_graph_flag_does_not_confirm_the_task_manager(self, tmp_path: Path) -> None:
        connection_url = _seed_task_manager_database(path=tmp_path / "task-manager.db")

        result = self._invoke(connection_url=connection_url, args=["--yes-graph"], user_input="n\n")

        assert result.exit_code == 1, result.output
        assert "Delete all data from the task manager database?" in result.output
        assert _count_flows(connection_url=connection_url) == 1
