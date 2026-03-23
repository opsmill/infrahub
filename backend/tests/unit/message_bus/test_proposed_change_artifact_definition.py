from __future__ import annotations

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.message_bus.types import ProposedChangeArtifactDefinition


def _make_definition(**overrides: object) -> ProposedChangeArtifactDefinition:
    defaults = {
        "definition_id": "def-1",
        "definition_name": "test-def",
        "artifact_name": "test-artifact",
        "query_name": "my-query",
        "query_id": "query-1",
        "query_models": [],
        "query_payload": "query { }",
        "repository_id": "repo-1",
        "transform_kind": InfrahubKind.TRANSFORMJINJA2,
        "content_type": "text/plain",
        "timeout": 30,
    }
    defaults.update(overrides)
    return ProposedChangeArtifactDefinition(**defaults)


class TestTransformLocation:
    def test_jinja2_returns_template_path(self) -> None:
        defn = _make_definition(
            transform_kind=InfrahubKind.TRANSFORMJINJA2,
            template_path="templates/report.j2",
        )
        assert defn.transform_location == "templates/report.j2"

    def test_python_returns_file_class(self) -> None:
        defn = _make_definition(
            transform_kind=InfrahubKind.TRANSFORMPYTHON,
            file_path="transforms/my_transform.py",
            class_name="MyTransform",
        )
        assert defn.transform_location == "transforms/my_transform.py::MyTransform"

    def test_ai_returns_prompt_template_path(self) -> None:
        defn = _make_definition(
            transform_kind=InfrahubKind.TRANSFORMAI,
            prompt_template_path="prompts/report.jinja2",
        )
        assert defn.transform_location == "prompts/report.jinja2"

    def test_unknown_kind_raises(self) -> None:
        defn = _make_definition(transform_kind="SomeUnknownKind")
        with pytest.raises(ValueError, match="Invalid kind for Transform"):
            _ = defn.transform_location


class TestAIFieldDefaults:
    def test_defaults(self) -> None:
        defn = _make_definition(transform_kind=InfrahubKind.TRANSFORMAI)
        assert not defn.prompt_template_path
        assert not defn.ai_model
        assert defn.ai_temperature == 100
        assert defn.ai_max_tokens == 4096
        assert defn.ai_output_format == "markdown"

    def test_custom_values(self) -> None:
        defn = _make_definition(
            transform_kind=InfrahubKind.TRANSFORMAI,
            prompt_template_path="prompts/custom.jinja2",
            ai_model="claude-opus-4-20250514",
            ai_temperature=50,
            ai_max_tokens=8192,
            ai_output_format="csv",
        )
        assert defn.prompt_template_path == "prompts/custom.jinja2"
        assert defn.ai_model == "claude-opus-4-20250514"
        assert defn.ai_temperature == 50
        assert defn.ai_max_tokens == 8192
        assert defn.ai_output_format == "csv"
