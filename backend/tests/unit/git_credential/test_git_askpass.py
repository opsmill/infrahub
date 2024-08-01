from typer.testing import CliRunner

from infrahub.git_credential.askpass import app

runner = CliRunner(mix_stderr=False)


def test_askpass_username(mock_core_schema_01, mock_repositories_query, mock_credential_query):
    input_data = "Username for 'https://github.com/opsmill/infrahub-demo-edge.git'"

    result = runner.invoke(app=app, args=[input_data], env={"INFRAHUB_INSERT_TRACKER": "true"}, catch_exceptions=False)
    assert not result.stderr
    assert result.stdout == "myusername\n"
    assert result.exit_code == 0


def test_askpass_password(mock_core_schema_01, mock_repositories_query, mock_credential_query):
    input_data = "Password for 'https://username@github.com/opsmill/infrahub-demo-edge.git'"

    result = runner.invoke(app=app, args=[input_data], env={"INFRAHUB_INSERT_TRACKER": "true"}, catch_exceptions=False)
    assert not result.stderr
    assert result.stdout == "mypassword\n"
    assert result.exit_code == 0
