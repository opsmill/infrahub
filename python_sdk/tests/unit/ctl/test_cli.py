from typer.testing import CliRunner

from infrahub_ctl.cli import app

runner = CliRunner()


def test_main_app():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "[OPTIONS] COMMAND [ARGS]" in result.stdout


def test_validate_all_commands_have_names():
    assert app.registered_commands
    for command in app.registered_commands:
        assert command.name


def test_validate_all_groups_have_names():
    assert app.registered_groups
    for group in app.registered_groups:
        assert group.name
