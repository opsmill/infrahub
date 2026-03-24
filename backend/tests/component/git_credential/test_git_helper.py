from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

# This patch prevents `OSError: pytest: reading from stdin while output is captured!  Consider using `-s`.`
# to be raised at import time. Patching is not an issue as `sys.stdin` is not used
# as runner.invoke also patches `sys.stdin`.
with patch("sys.stdin"):
    from infrahub.git_credential.helper import app, parse_helper_get_input

runner = CliRunner(mix_stderr=False)


def test_parse_helper_get_input() -> None:
    data_in = "protocol=https\nhost=github.com\npath=opsmill/infrahub-demo-edge.git"
    assert parse_helper_get_input(text=data_in) == "https://github.com/opsmill/infrahub-demo-edge.git"

    with pytest.raises(ValueError):
        data_in = "protocol=https\nhost=github.com"
        parse_helper_get_input(text=data_in)

    with pytest.raises(ValueError):
        data_in = "host=github.com\npath=opsmill/infrahub-demo-edge.git"
        parse_helper_get_input(text=data_in)


def test_get_with_path(
    mock_core_schema_01: HTTPXMock, mock_repositories_query: HTTPXMock, mock_credential_query: HTTPXMock
) -> None:
    input_data = "protocol=https\nhost=github.com\npath=opsmill/infrahub-demo-edge.git"

    result = runner.invoke(
        app=app, args=["get", input_data], env={"INFRAHUB_INSERT_TRACKER": "true"}, catch_exceptions=False
    )
    assert not result.stderr
    assert result.stdout == "username=myusername\npassword=mypassword\n"
    assert result.exit_code == 0


def test_get_no_path() -> None:
    input_data = "protocol=https\nhost=github.com"

    result = runner.invoke(app=app, args=["get", input_data])
    assert not result.stderr
    assert "Git usehttppath must be enabled to use this helper." in result.stdout
    assert result.exit_code == 1
