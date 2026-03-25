from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from infrahub_sdk.schema.repository import InfrahubAICheckDefinitionConfig

from infrahub.git.integrator import InfrahubRepositoryAICheck, InfrahubRepositoryIntegrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_attr(value: Any) -> MagicMock:
    attr = MagicMock()
    attr.value = value
    return attr


def _make_rel(id_value: str | None) -> MagicMock:
    rel = MagicMock()
    rel.id = id_value
    return rel


def _make_existing_check(  # noqa: PLR0913
    *,
    name: str = "test-ai-check",
    description: str | None = None,
    prompt_template_path: str = "checks/validate.jinja2",
    query_id: str | None = None,
    model: str = "claude-sonnet-4-5-20250929",
    temperature: int = 0,
    max_tokens: int = 4096,
    timeout: int = 60,
) -> MagicMock:
    check = MagicMock()
    check.name = _make_attr(name)
    check.description = _make_attr(description)
    check.prompt_template_path = _make_attr(prompt_template_path)
    check.query = _make_rel(query_id)
    check.model = _make_attr(model)
    check.temperature = _make_attr(temperature)
    check.max_tokens = _make_attr(max_tokens)
    check.timeout = _make_attr(timeout)
    check.save = AsyncMock()
    return check


def _make_local_check(  # noqa: PLR0913
    *,
    name: str = "test-ai-check",
    description: str | None = None,
    prompt_template_path: str = "checks/validate.jinja2",
    query: str | None = None,
    model: str = "claude-sonnet-4-5-20250929",
    temperature: int = 0,
    max_tokens: int = 4096,
    timeout: int = 60,
    repository: str = "repo-uuid",
) -> InfrahubRepositoryAICheck:
    return InfrahubRepositoryAICheck(
        name=name,
        query=query,
        prompt_template_path=Path(prompt_template_path),
        description=description,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        repository=repository,
    )


# ---------------------------------------------------------------------------
# Config payload tests
# ---------------------------------------------------------------------------


class TestAICheckDefinitionConfigPayload:
    def test_payload_includes_all_fields(self) -> None:
        config = InfrahubAICheckDefinitionConfig(
            name="test-check",
            prompt_template_path=Path("checks/validate.jinja2"),
            model="claude-sonnet-4-5-20250929",
            temperature=0,
            max_tokens=4096,
            timeout=60,
        )
        payload = config.payload
        assert payload["name"] == "test-check"
        assert payload["prompt_template_path"] == "checks/validate.jinja2"
        assert payload["model"] == "claude-sonnet-4-5-20250929"
        assert payload["temperature"] == 0
        assert payload["max_tokens"] == 4096
        assert payload["timeout"] == 60

    def test_payload_excludes_none_query(self) -> None:
        config = InfrahubAICheckDefinitionConfig(
            name="test-check",
            prompt_template_path=Path("checks/validate.jinja2"),
        )
        payload = config.payload
        assert "query" not in payload

    def test_payload_includes_query_when_set(self) -> None:
        config = InfrahubAICheckDefinitionConfig(
            name="test-check",
            query="my-query",
            prompt_template_path=Path("checks/validate.jinja2"),
        )
        payload = config.payload
        assert payload["query"] == "my-query"

    def test_prompt_template_path_value_is_string(self) -> None:
        config = InfrahubAICheckDefinitionConfig(
            name="test-check",
            prompt_template_path=Path("checks/validate.jinja2"),
        )
        assert isinstance(config.prompt_template_path_value, str)
        assert config.prompt_template_path_value == "checks/validate.jinja2"


# ---------------------------------------------------------------------------
# Compare tests
# ---------------------------------------------------------------------------


class TestCompareAICheckDefinition:
    async def test_match_returns_true(self) -> None:
        existing = _make_existing_check()
        local = _make_local_check()

        result = await InfrahubRepositoryIntegrator.compare_ai_check_definition(
            existing_check=existing, local_check=local
        )
        assert result is True

    async def test_mismatch_description_returns_false(self) -> None:
        existing = _make_existing_check(description="old desc")
        local = _make_local_check(description="new desc")

        result = await InfrahubRepositoryIntegrator.compare_ai_check_definition(
            existing_check=existing, local_check=local
        )
        assert result is False

    async def test_mismatch_model_returns_false(self) -> None:
        existing = _make_existing_check(model="claude-sonnet-4-5-20250929")
        local = _make_local_check(model="claude-opus-4-20250514")

        result = await InfrahubRepositoryIntegrator.compare_ai_check_definition(
            existing_check=existing, local_check=local
        )
        assert result is False

    async def test_mismatch_temperature_returns_false(self) -> None:
        existing = _make_existing_check(temperature=0)
        local = _make_local_check(temperature=50)

        result = await InfrahubRepositoryIntegrator.compare_ai_check_definition(
            existing_check=existing, local_check=local
        )
        assert result is False

    async def test_mismatch_max_tokens_returns_false(self) -> None:
        existing = _make_existing_check(max_tokens=4096)
        local = _make_local_check(max_tokens=8192)

        result = await InfrahubRepositoryIntegrator.compare_ai_check_definition(
            existing_check=existing, local_check=local
        )
        assert result is False

    async def test_mismatch_timeout_returns_false(self) -> None:
        existing = _make_existing_check(timeout=60)
        local = _make_local_check(timeout=120)

        result = await InfrahubRepositoryIntegrator.compare_ai_check_definition(
            existing_check=existing, local_check=local
        )
        assert result is False

    async def test_mismatch_prompt_template_path_returns_false(self) -> None:
        existing = _make_existing_check(prompt_template_path="checks/old.jinja2")
        local = _make_local_check(prompt_template_path="checks/new.jinja2")

        result = await InfrahubRepositoryIntegrator.compare_ai_check_definition(
            existing_check=existing, local_check=local
        )
        assert result is False

    async def test_mismatch_query_returns_false(self) -> None:
        existing = _make_existing_check(query_id="old-query-uuid")
        local = _make_local_check(query="new-query-uuid")

        result = await InfrahubRepositoryIntegrator.compare_ai_check_definition(
            existing_check=existing, local_check=local
        )
        assert result is False

    async def test_both_no_query_returns_true(self) -> None:
        existing = _make_existing_check(query_id=None)
        local = _make_local_check(query=None)

        result = await InfrahubRepositoryIntegrator.compare_ai_check_definition(
            existing_check=existing, local_check=local
        )
        assert result is True


# ---------------------------------------------------------------------------
# Update tests
# ---------------------------------------------------------------------------


class TestUpdateAICheckDefinition:
    async def test_updates_description_and_saves(self) -> None:
        existing = _make_existing_check(description="old")
        local = _make_local_check(description="new")

        integrator = MagicMock(spec=InfrahubRepositoryIntegrator)
        integrator.id = "repo-uuid"
        integrator.update_ai_check_definition = InfrahubRepositoryIntegrator.update_ai_check_definition.__get__(
            integrator, InfrahubRepositoryIntegrator
        )

        await integrator.update_ai_check_definition(existing_check=existing, local_check=local)

        assert existing.description.value == "new"
        existing.save.assert_awaited_once()

    async def test_updates_model(self) -> None:
        existing = _make_existing_check(model="claude-sonnet-4-5-20250929")
        local = _make_local_check(model="claude-opus-4-20250514")

        integrator = MagicMock(spec=InfrahubRepositoryIntegrator)
        integrator.id = "repo-uuid"
        integrator.update_ai_check_definition = InfrahubRepositoryIntegrator.update_ai_check_definition.__get__(
            integrator, InfrahubRepositoryIntegrator
        )

        await integrator.update_ai_check_definition(existing_check=existing, local_check=local)

        assert existing.model.value == "claude-opus-4-20250514"
        existing.save.assert_awaited_once()

    async def test_updates_multiple_fields(self) -> None:
        existing = _make_existing_check(
            description="old desc",
            temperature=0,
            max_tokens=4096,
        )
        local = _make_local_check(
            description="new desc",
            temperature=50,
            max_tokens=8192,
        )

        integrator = MagicMock(spec=InfrahubRepositoryIntegrator)
        integrator.id = "repo-uuid"
        integrator.update_ai_check_definition = InfrahubRepositoryIntegrator.update_ai_check_definition.__get__(
            integrator, InfrahubRepositoryIntegrator
        )

        await integrator.update_ai_check_definition(existing_check=existing, local_check=local)

        assert existing.description.value == "new desc"
        assert existing.temperature.value == 50
        assert existing.max_tokens.value == 8192
        existing.save.assert_awaited_once()

    async def test_no_change_when_all_match(self) -> None:
        existing = _make_existing_check()
        local = _make_local_check()

        integrator = MagicMock(spec=InfrahubRepositoryIntegrator)
        integrator.id = "repo-uuid"
        integrator.update_ai_check_definition = InfrahubRepositoryIntegrator.update_ai_check_definition.__get__(
            integrator, InfrahubRepositoryIntegrator
        )

        await integrator.update_ai_check_definition(existing_check=existing, local_check=local)

        existing.save.assert_awaited_once()
