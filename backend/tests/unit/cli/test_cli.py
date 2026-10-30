import re
from unittest.mock import patch

from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL, temporary_settings
from typer.testing import CliRunner

from infrahub.cli import app

runner = CliRunner()

ANSI_STYLE = re.compile(r"\x1b\[[0-9;]*m")
COMMAND_ROW = re.compile(r"^│ (\S+)\s+(.*?)\s*│$", flags=re.MULTILINE)


def _plain(output: str) -> str:
    """Strip the ANSI styling Rich adds when the terminal, or the CI runner, advertises colors."""
    return ANSI_STYLE.sub("", output)


def _listed(output: str) -> dict[str, str]:
    """Map each name in the help panels to its one-line description."""
    return dict(COMMAND_ROW.findall(_plain(output)))


def test_main_app() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "[OPTIONS] COMMAND [ARGS]" in result.stdout


def test_the_help_lists_the_task_manager_commands() -> None:
    main_help = runner.invoke(app, ["--help"], env={"COLUMNS": "200"})
    tasks_help = runner.invoke(app, ["tasks", "--help"], env={"COLUMNS": "200"})

    assert (main_help.exit_code, _listed(main_help.stdout).get("tasks")) == (
        0,
        "Manage the task manager and its task history.",
    )
    assert (tasks_help.exit_code, _listed(tasks_help.stdout).get("flush")) == (
        0,
        "Delete old task runs, or mark stale task runs as crashed.",
    )


def test_db_app() -> None:
    result = runner.invoke(app, ["db", "--help"])
    assert result.exit_code == 0
    assert "[OPTIONS] COMMAND [ARGS]" in result.stdout


def test_server_app() -> None:
    result = runner.invoke(app, ["server", "--help"])
    assert result.exit_code == 0
    assert "[OPTIONS] COMMAND [ARGS]" in result.stdout


def test_db_reset_help() -> None:
    result = runner.invoke(app, ["db", "reset", "--help"])
    assert result.exit_code == 0
    assert "--yes-graph" in _plain(result.stdout)
    assert "--yes-task-manager" in _plain(result.stdout)


def test_db_reset_without_any_configured_database() -> None:
    with (
        patch("infrahub.cli.db.is_graph_database_configured", return_value=False),
        temporary_settings(updates={PREFECT_API_DATABASE_CONNECTION_URL: None}),
    ):
        result = runner.invoke(app, ["db", "reset"])
    assert result.exit_code == 1
    assert "No database is configured" in result.output


def test_db_reset_rejects_an_unsupported_task_manager_database() -> None:
    with (
        patch("infrahub.cli.db.is_graph_database_configured", return_value=False),
        temporary_settings(updates={PREFECT_API_DATABASE_CONNECTION_URL: "mysql+pymysql://user:pw@db/prefect"}),
    ):
        result = runner.invoke(app, ["db", "reset"])
    assert result.exit_code == 1
    assert "Unsupported task manager database" in result.output
