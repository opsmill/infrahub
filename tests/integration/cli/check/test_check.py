from typer.testing import CliRunner

from infrahub.cli.check import app

runner = CliRunner()


def test_run_empty():

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["run", "--format-json"])
        assert result.exit_code == 1
        assert "No check found" in result.stdout


# def test_run_with_check(dataset01):

#     runner = CliRunner()

#     with runner.isolated_filesystem():
#         copy_project_to_tmp_dir("project_02")
#         result = runner.invoke(app, ["run", "--format-json"])
#         assert result.exit_code == 1
#         assert "No check found" in result.stdout
