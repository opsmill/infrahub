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

    assert result.exit_code == 1
    assert "Empty YAML/JSON file" in result.stdout


def test_schema_load_one_valid(httpx_mock: HTTPXMock):
    fixture_file = get_fixtures_dir() / "models" / "valid_model_01.json"

    httpx_mock.add_response(
        method="POST",
        url="http://mock/api/schema/load?branch=main",
        status_code=200,
        json={
            "hash": "497c17fbe915062c8c5a698be62130e4",
            "previous_hash": "d3f7f4e7161f0ae6538a01d5a42dc661",
            "diff": {
                "added": {"InfraDevice": {"added": {}, "changed": {}, "removed": {}}},
                "changed": {},
                "removed": {},
            },
            "schema_updated": True,
        },
    )
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


def test_schema_load_notvalid_namespace(httpx_mock: HTTPXMock):
    fixture_file = get_fixtures_dir() / "models" / "non_valid_namespace.json"

    httpx_mock.add_response(
        method="POST",
        url="http://mock/api/schema/load?branch=main",
        status_code=422,
        json={
            "detail": [
                {
                    "type": "string_pattern_mismatch",
                    "loc": ["body", "schemas", 0, "nodes", 0, "namespace"],
                    "msg": "String should match pattern '^[A-Z][a-z0-9]+$'",
                    "input": "OuT",
                    "ctx": {"pattern": "^[A-Z][a-z0-9]+$"},
                    "url": "https://errors.pydantic.dev/2.7/v/string_pattern_mismatch",
                },
                {
                    "type": "value_error",
                    "loc": ["body", "schemas", 0, "nodes", 0, "attributes", 0, "kind"],
                    "msg": "Value error, Only valid Attribute Kind are : ['ID', 'Dropdown'] ",
                    "input": "NotValid",
                    "ctx": {"error": {}},
                    "url": "https://errors.pydantic.dev/2.7/v/value_error",
                },
            ]
        },
    )
    result = runner.invoke(app=app, args=["load", str(fixture_file)])

    assert result.exit_code == 1

    expected_result = (
        "\x1b[31mUnable to load the schema:\x1b[0m\n "
        " Node: OuTDevice | namespace \x1b[1m(\x1b[0mOuT\x1b[1m)\x1b[0m | "
        "String should match pattern \x1b[32m'^\x1b[0m\x1b[32m[\x1b[0m\x1b[32mA-Z\x1b[0m\x1b[32m]\x1b[0m\x1b[32m+$'\x1b[0m "
        "\x1b[1m(\x1b[0mstring_pattern_mismatch\x1b[1m)\x1b[0m\n "
        " Node: OuTDevice | Attribute: name \x1b[1m(\x1b[0mNotValid\x1b[1m)\x1b[0m | "
        "Value error, Only valid Attribute Kind are : \x1b[1m[\x1b[0m\x1b[32m'ID'\x1b[0m, \x1b[32m'Dropdown'\x1b[0m\x1b[1m]\x1b[0m "
        " \x1b[1m(\x1b[0mvalue_error\x1b[1m)\x1b[0m\n\x1b[1;31m1\x1b[0m\n"
    )
    assert expected_result == result.stdout

    content = httpx_mock.get_requests()[0].content.decode("utf8")
    content_json = yaml.safe_load(content)
    fixture_file_content = yaml.safe_load(
        fixture_file.read_text(encoding="utf-8"),
    )
    assert content_json == {"schemas": [fixture_file_content]}
