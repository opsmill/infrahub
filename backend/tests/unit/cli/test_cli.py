from unittest.mock import patch

from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL, temporary_settings
from typer.testing import CliRunner

from infrahub.cli import app

runner = CliRunner()


def test_main_app() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "[OPTIONS] COMMAND [ARGS]" in result.stdout


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
    assert "--yes-graph" in result.stdout
    assert "--yes-task-manager" in result.stdout


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
