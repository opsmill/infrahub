import pytest
from typer.testing import CliRunner

from infrahub.git_credential.helper import app, parse_helper_get_input

runner = CliRunner(mix_stderr=False)


def test_parse_helper_get_input():
    data_in = "protocol=https\nhost=github.com\npath=opsmill/infrahub-demo-edge.git"
    assert parse_helper_get_input(text=data_in) == "https://github.com/opsmill/infrahub-demo-edge.git"

    with pytest.raises(ValueError):
        data_in = "protocol=https\nhost=github.com"
        parse_helper_get_input(text=data_in)

    with pytest.raises(ValueError):
        data_in = "host=github.com\npath=opsmill/infrahub-demo-edge.git"
        parse_helper_get_input(text=data_in)


def test_get_with_path(mock_core_schema_01, mock_repositories_query, mock_credential_query):
    input_data = "protocol=https\nhost=github.com\npath=opsmill/infrahub-demo-edge.git"

    result = runner.invoke(
        app=app, args=["get", input_data], env={"INFRAHUB_INSERT_TRACKER": "true"}, catch_exceptions=False
    )
    assert not result.stderr
    assert result.stdout == "username=myusername\npassword=mypassword\n"
    assert result.exit_code == 0


def test_get_no_path():
    input_data = "protocol=https\nhost=github.com"

    result = runner.invoke(app=app, args=["get", input_data])
    assert not result.stderr
    assert "Git usehttppath must be enabled to use this helper." in result.stdout
    assert result.exit_code == 1
