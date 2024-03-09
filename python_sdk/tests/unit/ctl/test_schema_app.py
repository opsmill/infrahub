import pytest
import yaml
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from infrahub_sdk.ctl.schema import app
from infrahub_sdk.ctl.utils import get_fixtures_dir

runner = CliRunner()


def test_schema_load_empty(httpx_mock: HTTPXMock):
    fixture_file = get_fixtures_dir() / "models" / "empty.json"
    result = runner.invoke(app=app, args=["load", str(fixture_file)])

    assert result.exit_code == 2
    assert "is empty" in result.stdout


def test_schema_load_one_valid(httpx_mock: HTTPXMock):
    fixture_file = get_fixtures_dir() / "models" / "valid_model_01.json"

    httpx_mock.add_response(method="POST", url="http://mock/api/schema/load?branch=main", status_code=202)
    result = runner.invoke(app=app, args=["load", str(fixture_file)])

    assert result.exit_code == 0
    assert f"schema '{fixture_file}' loaded successfully" in result.stdout.replace("\n", "")

    content = httpx_mock.get_requests()[0].content.decode("utf8")
    content_json = yaml.safe_load(content)
    fixture_file_content = yaml.safe_load(
        fixture_file.read_text(encoding="utf-8"),
    )
    assert content_json == {"schemas": [fixture_file_content]}


@pytest.mark.xfail(reason="FIXME: work locally but not in CI")
def test_schema_load_multiple(httpx_mock: HTTPXMock):
    fixture_file1 = get_fixtures_dir() / "models" / "valid_schemas" / "contract.yml"
    fixture_file2 = get_fixtures_dir() / "models" / "valid_schemas" / "rack.yml"

    httpx_mock.add_response(method="POST", url="http://mock/api/schema/load?branch=main", status_code=202)
    result = runner.invoke(app=app, args=["load", str(fixture_file1), str(fixture_file2)])

    assert result.exit_code == 0
    assert f"schema '{fixture_file1}' loaded successfully" in result.stdout.replace("\n", "")
    assert f"schema '{fixture_file2}' loaded successfully" in result.stdout.replace("\n", "")

    content = httpx_mock.get_requests()[0].content.decode("utf8")
    content_json = yaml.safe_load(content)
    fixture_file1_content = yaml.safe_load(fixture_file1.read_text(encoding="utf-8"))
    fixture_file2_content = yaml.safe_load(fixture_file2.read_text(encoding="utf-8"))
    assert content_json == {"schemas": [fixture_file1_content, fixture_file2_content]}
