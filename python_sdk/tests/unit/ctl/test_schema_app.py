import yaml
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from infrahub_sdk.ctl.schema import app
from infrahub_sdk.ctl.utils import get_fixtures_dir
from tests.helpers.cli import remove_ansi_color

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
    assert f"schema '{fixture_file}' loaded successfully" in remove_ansi_color(result.stdout.replace("\n", ""))

    content = httpx_mock.get_requests()[0].content.decode("utf8")
    content_json = yaml.safe_load(content)
    fixture_file_content = yaml.safe_load(
        fixture_file.read_text(encoding="utf-8"),
    )
    assert content_json == {"schemas": [fixture_file_content]}


def test_schema_load_multiple(httpx_mock: HTTPXMock):
    fixture_file1 = get_fixtures_dir() / "models" / "valid_schemas" / "contract.yml"
    fixture_file2 = get_fixtures_dir() / "models" / "valid_schemas" / "rack.yml"

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
    result = runner.invoke(app=app, args=["load", str(fixture_file1), str(fixture_file2)])

    assert result.exit_code == 0
    clean_output = remove_ansi_color(result.stdout.replace("\n", ""))
    assert f"schema '{fixture_file1}' loaded successfully" in clean_output
    assert f"schema '{fixture_file2}' loaded successfully" in clean_output

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

    clean_output = remove_ansi_color(result.stdout.replace("\n", ""))
    expected_result = (
        "Unable to load the schema:  Node: OuTDevice | "
        "namespace (OuT) | String should match pattern '^[A-Z]+$' (string_pattern_mismatch) "
        " Node: OuTDevice | Attribute: name (NotValid) | Value error, Only valid Attribute Kind "
        "are : ['ID', 'Dropdown']  (value_error)"
    )
    assert expected_result == clean_output

    content = httpx_mock.get_requests()[0].content.decode("utf8")
    content_json = yaml.safe_load(content)
    fixture_file_content = yaml.safe_load(
        fixture_file.read_text(encoding="utf-8"),
    )
    assert content_json == {"schemas": [fixture_file_content]}
