from typer.testing import CliRunner

from infrahub.cli import app

runner = CliRunner()


def test_main_app():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "[OPTIONS] COMMAND [ARGS]" in result.stdout


def test_db_app():
    result = runner.invoke(app, ["db", "--help"])
    assert result.exit_code == 0
    assert "[OPTIONS] COMMAND [ARGS]" in result.stdout


def test_git_agent_app():
    result = runner.invoke(app, ["git-agent", "--help"])
    assert result.exit_code == 0
    assert "[OPTIONS] COMMAND [ARGS]" in result.stdout


def test_server_app():
    result = runner.invoke(app, ["server", "--help"])
    assert result.exit_code == 0
    assert "[OPTIONS] COMMAND [ARGS]" in result.stdout
