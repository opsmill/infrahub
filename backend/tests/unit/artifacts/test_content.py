from __future__ import annotations

import pytest

from infrahub.artifacts.content import format_artifact_content


@pytest.mark.parametrize(
    ("content", "content_type", "expected"),
    [
        pytest.param(
            [{"name": "edge-01"}], "application/json", '[\n  {\n    "name": "edge-01"\n  }\n]', id="json_list"
        ),
        pytest.param({"name": "edge-01"}, "application/json", '{\n  "name": "edge-01"\n}', id="json_mapping"),
        pytest.param(["edge-01"], "application/yaml", "- edge-01\n", id="yaml_list"),
        pytest.param("hostname edge-01\n", "text/plain", "hostname edge-01\n", id="text"),
    ],
)
def test_structured_content_is_serialized_for_json_and_yaml(content: object, content_type: str, expected: str) -> None:
    assert format_artifact_content(content=content, content_type=content_type) == expected
