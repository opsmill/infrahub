from typer.testing import CliRunner

from infrahub_ctl.cli import app

runner = CliRunner()


def test_main_app():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "[OPTIONS] COMMAND [ARGS]" in result.stdout
