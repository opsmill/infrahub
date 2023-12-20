import os
from pathlib import Path

import pytest
import yaml
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from infrahub_ctl.schema import app
from infrahub_ctl.utils import get_fixtures_dir

runner = CliRunner()


def test_schema_load_one_valid(httpx_mock: HTTPXMock):
    fixture_file = os.path.join(get_fixtures_dir(), "models", "valid_model_01.json")

    httpx_mock.add_response(method="POST", url="http://mock/api/schema/load?branch=main", status_code=202)
    result = runner.invoke(app=app, args=["load", fixture_file])

    assert result.exit_code == 0
    assert f"schema '{fixture_file}' loaded successfully" in result.stdout.replace("\n", "")

    content = httpx_mock.get_requests()[0].content.decode("utf8")
    content_json = yaml.safe_load(content)
    fixture_file_content = yaml.safe_load(
        Path(fixture_file).read_text(encoding="utf-8"),
    )
    assert content_json == {"schemas": [fixture_file_content]}


@pytest.mark.xfail(reason="FIXME: work locally but not in CI")
def test_schema_load_multiple(httpx_mock: HTTPXMock):
    fixture_file1 = os.path.join(get_fixtures_dir(), "models", "valid_schemas", "contract.yml")
    fixture_file2 = os.path.join(get_fixtures_dir(), "models", "valid_schemas", "rack.yml")

    httpx_mock.add_response(method="POST", url="http://mock/api/schema/load?branch=main", status_code=202)
    result = runner.invoke(app=app, args=["load", fixture_file1, fixture_file2])

    assert result.exit_code == 0
    assert f"schema '{fixture_file1}' loaded successfully" in result.stdout.replace("\n", "")
    assert f"schema '{fixture_file2}' loaded successfully" in result.stdout.replace("\n", "")

    content = httpx_mock.get_requests()[0].content.decode("utf8")
    content_json = yaml.safe_load(content)
    fixture_file1_content = yaml.safe_load(Path(fixture_file1).read_text(encoding="utf-8"))
    fixture_file2_content = yaml.safe_load(Path(fixture_file2).read_text(encoding="utf-8"))
    assert content_json == {"schemas": [fixture_file1_content, fixture_file2_content]}
