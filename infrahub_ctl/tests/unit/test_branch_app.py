from typer.testing import CliRunner

from infrahub_ctl.branch import app

runner = CliRunner()


def test_branch_list(mock_branches_list_query):
    result = runner.invoke(app=app, args=["list"])
    assert result.exit_code == 0
    assert "cr1234" in result.stdout
