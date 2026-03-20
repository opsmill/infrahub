from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from infrahub_sdk.schema import InfrahubSchemaSync
from infrahub_sdk.schema.repository import InfrahubAITransformConfig

from infrahub.git.integrator import InfrahubRepositoryAI, InfrahubRepositoryIntegrator

# ---------------------------------------------------------------------------
# Test (a): InfrahubAITransformConfig.payload includes result_kind
# ---------------------------------------------------------------------------


class TestAITransformConfigPayload:
    def test_payload_includes_result_kind(self) -> None:
        config = InfrahubAITransformConfig(
            name="test-transform",
            query="my-query",
            prompt_template_path=Path("prompts/test.jinja2"),
            result_kind="TestFileObject",
        )
        payload = config.payload
        assert "result_kind" in payload
        assert payload["result_kind"] == "TestFileObject"

    def test_payload_excludes_result_kind_when_none(self) -> None:
        config = InfrahubAITransformConfig(
            name="test-transform",
            query="my-query",
            prompt_template_path=Path("prompts/test.jinja2"),
        )
        payload = config.payload
        assert "result_kind" not in payload

    def test_model_dump_exclude_none_includes_result_kind(self) -> None:
        config = InfrahubAITransformConfig(
            name="test-transform",
            query="my-query",
            prompt_template_path=Path("prompts/test.jinja2"),
            result_kind="TestFileObject",
        )
        dumped = config.model_dump(exclude_none=True)
        assert "result_kind" in dumped
        assert dumped["result_kind"] == "TestFileObject"

    def test_model_dump_exclude_none_omits_result_kind_when_none(self) -> None:
        config = InfrahubAITransformConfig(
            name="test-transform",
            query="my-query",
            prompt_template_path=Path("prompts/test.jinja2"),
        )
        dumped = config.model_dump(exclude_none=True)
        assert "result_kind" not in dumped


# ---------------------------------------------------------------------------
# Helpers: mock a CoreTransformAI-like object
# ---------------------------------------------------------------------------


def _make_attr(value: Any) -> MagicMock:
    attr = MagicMock()
    attr.value = value
    return attr


def _make_rel(id_value: str) -> MagicMock:
    rel = MagicMock()
    rel.id = id_value
    return rel


def _make_existing_transform(  # noqa: PLR0913
    *,
    name: str = "test-transform",
    description: str | None = None,
    prompt_template_path: str = "prompts/test.jinja2",
    query_id: str = "query-uuid",
    model: str = "claude-sonnet-4-5-20250929",
    temperature: int = 100,
    max_tokens: int = 4096,
    output_format: str = "markdown",
    result_kind: str | None = None,
) -> MagicMock:
    transform = MagicMock()
    transform.name = _make_attr(name)
    transform.description = _make_attr(description)
    transform.prompt_template_path = _make_attr(prompt_template_path)
    transform.query = _make_rel(query_id)
    transform.model = _make_attr(model)
    transform.temperature = _make_attr(temperature)
    transform.max_tokens = _make_attr(max_tokens)
    transform.output_format = _make_attr(output_format)
    transform.result_kind = _make_attr(result_kind)
    transform.save = AsyncMock()
    return transform


def _make_local_transform(  # noqa: PLR0913
    *,
    name: str = "test-transform",
    description: str | None = None,
    prompt_template_path: str = "prompts/test.jinja2",
    query: str = "query-uuid",
    model: str = "claude-sonnet-4-5-20250929",
    temperature: int = 100,
    max_tokens: int = 4096,
    output_format: str = "markdown",
    result_kind: str | None = None,
    repository: str = "repo-uuid",
) -> InfrahubRepositoryAI:
    return InfrahubRepositoryAI(
        name=name,
        query=query,
        prompt_template_path=Path(prompt_template_path),
        description=description,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        output_format=output_format,
        result_kind=result_kind,
        repository=repository,
    )


# ---------------------------------------------------------------------------
# Test (b): compare_ai_transform detects result_kind mismatch
# ---------------------------------------------------------------------------


class TestCompareAITransform:
    async def test_match_returns_true(self) -> None:
        existing = _make_existing_transform(result_kind="TestFileObject")
        local = _make_local_transform(result_kind="TestFileObject")

        result = await InfrahubRepositoryIntegrator.compare_ai_transform(
            existing_transform=existing, local_transform=local
        )
        assert result is True

    async def test_mismatch_result_kind_returns_false(self) -> None:
        existing = _make_existing_transform(result_kind=None)
        local = _make_local_transform(result_kind="TestFileObject")

        result = await InfrahubRepositoryIntegrator.compare_ai_transform(
            existing_transform=existing, local_transform=local
        )
        assert result is False

    async def test_mismatch_result_kind_different_values_returns_false(self) -> None:
        existing = _make_existing_transform(result_kind="OldKind")
        local = _make_local_transform(result_kind="NewKind")

        result = await InfrahubRepositoryIntegrator.compare_ai_transform(
            existing_transform=existing, local_transform=local
        )
        assert result is False

    async def test_both_none_returns_true(self) -> None:
        existing = _make_existing_transform(result_kind=None)
        local = _make_local_transform(result_kind=None)

        result = await InfrahubRepositoryIntegrator.compare_ai_transform(
            existing_transform=existing, local_transform=local
        )
        assert result is True

    async def test_mismatch_model_returns_false(self) -> None:
        existing = _make_existing_transform(model="claude-sonnet-4-5-20250929")
        local = _make_local_transform(model="claude-opus-4-20250514")

        result = await InfrahubRepositoryIntegrator.compare_ai_transform(
            existing_transform=existing, local_transform=local
        )
        assert result is False


# ---------------------------------------------------------------------------
# Test (c): update_ai_transform sets result_kind
# ---------------------------------------------------------------------------


class TestUpdateAITransform:
    async def test_sets_result_kind_and_saves(self) -> None:
        existing = _make_existing_transform(result_kind=None)
        local = _make_local_transform(result_kind="TestFileObject")

        integrator = MagicMock(spec=InfrahubRepositoryIntegrator)
        integrator.id = "repo-uuid"
        integrator.update_ai_transform = InfrahubRepositoryIntegrator.update_ai_transform.__get__(
            integrator, InfrahubRepositoryIntegrator
        )

        await integrator.update_ai_transform(existing_transform=existing, local_transform=local)

        assert existing.result_kind.value == "TestFileObject"
        existing.save.assert_awaited_once()

    async def test_no_change_when_result_kind_matches(self) -> None:
        existing = _make_existing_transform(result_kind="TestFileObject")
        local = _make_local_transform(result_kind="TestFileObject")

        integrator = MagicMock(spec=InfrahubRepositoryIntegrator)
        integrator.id = "repo-uuid"
        integrator.update_ai_transform = InfrahubRepositoryIntegrator.update_ai_transform.__get__(
            integrator, InfrahubRepositoryIntegrator
        )

        await integrator.update_ai_transform(existing_transform=existing, local_transform=local)

        assert existing.result_kind.value == "TestFileObject"
        existing.save.assert_awaited_once()

    async def test_updates_multiple_fields(self) -> None:
        existing = _make_existing_transform(
            description="old desc",
            model="claude-sonnet-4-5-20250929",
            result_kind=None,
        )
        local = _make_local_transform(
            description="new desc",
            model="claude-opus-4-20250514",
            result_kind="TestFileObject",
        )

        integrator = MagicMock(spec=InfrahubRepositoryIntegrator)
        integrator.id = "repo-uuid"
        integrator.update_ai_transform = InfrahubRepositoryIntegrator.update_ai_transform.__get__(
            integrator, InfrahubRepositoryIntegrator
        )

        await integrator.update_ai_transform(existing_transform=existing, local_transform=local)

        assert existing.description.value == "new desc"
        assert existing.model.value == "claude-opus-4-20250514"
        assert existing.result_kind.value == "TestFileObject"
        existing.save.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test (d): generate_payload_create includes result_kind
# ---------------------------------------------------------------------------


class TestGeneratePayloadCreate:
    def test_result_kind_in_payload(self) -> None:
        schema_manager = InfrahubSchemaSync(client=MagicMock())

        mock_schema = MagicMock()
        mock_schema.attribute_names = [
            "name",
            "description",
            "prompt_template_path",
            "model",
            "temperature",
            "max_tokens",
            "output_format",
            "result_kind",
        ]
        mock_schema.relationship_names = ["query", "repository"]
        mock_schema.get_relationship.return_value = MagicMock(cardinality="one")

        data = {
            "name": "test-transform",
            "prompt_template_path": "prompts/test.jinja2",
            "model": "claude-sonnet-4-5-20250929",
            "temperature": 100,
            "max_tokens": 4096,
            "output_format": "markdown",
            "result_kind": "TestFileObject",
            "query": "query-uuid",
            "repository": "repo-uuid",
        }

        result = schema_manager.generate_payload_create(
            schema=mock_schema, data=data, source="repo-uuid", is_protected=True
        )

        assert "result_kind" in result
        assert result["result_kind"]["value"] == "TestFileObject"
        assert result["result_kind"]["source"] == "repo-uuid"
        assert result["result_kind"]["is_protected"] is True

    def test_result_kind_not_in_payload_when_not_in_data(self) -> None:
        schema_manager = InfrahubSchemaSync(client=MagicMock())

        mock_schema = MagicMock()
        mock_schema.attribute_names = [
            "name",
            "prompt_template_path",
            "result_kind",
        ]
        mock_schema.relationship_names = ["query"]
        mock_schema.get_relationship.return_value = MagicMock(cardinality="one")

        data = {
            "name": "test-transform",
            "prompt_template_path": "prompts/test.jinja2",
            "query": "query-uuid",
        }

        result = schema_manager.generate_payload_create(
            schema=mock_schema, data=data, source="repo-uuid", is_protected=True
        )

        assert "result_kind" not in result
