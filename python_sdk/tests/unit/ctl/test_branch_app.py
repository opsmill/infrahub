from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from infrahub_sdk.ctl.branch import app

runner = CliRunner()

# pylint: disable=unused-argument


def test_branch_list(mock_branches_list_query):
    result = runner.invoke(app=app, args=["list"])
    assert result.exit_code == 0
    assert "cr1234" in result.stdout


def test_branch_create_no_auth(httpx_mock: HTTPXMock, authentication_error_payload):
    httpx_mock.add_response(
        status_code=401,
        method="POST",
        json=authentication_error_payload,
        match_headers={"X-Infrahub-Tracker": "mutation-branch-create"},
    )
    result = runner.invoke(app=app, args=["create", "branch2"])
    assert result.exit_code == 1
    assert "Authentication is required" in result.stdout


def test_branch_create_wrong_name(mock_branch_create_error):
    result = runner.invoke(app=app, args=["create", "branch2"])
    assert result.exit_code == 1
    assert 'invalid field name: string does not match regex "^[a-z][a-z0-9' in result.stdout.replace("\n", "")
