from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrahub.core.constants import ContentType, InfrahubKind
from infrahub.git.integrator import ArtifactGenerateResult, InfrahubRepositoryIntegrator


def _make_message(  # noqa: PLR0913
    *,
    transform_type: str = InfrahubKind.TRANSFORMAI,
    content_type: str = ContentType.TEXT_PLAIN.value,
    ai_model: str = "claude-sonnet-4-5-20250929",
    ai_temperature: float = 1.0,
    ai_max_tokens: int = 4096,
    ai_output_format: str = "markdown",
    transform_location: str = "prompts/report.jinja2",
    existing_checksum: str = "old-checksum",
) -> MagicMock:
    msg = MagicMock()
    msg.transform_type = transform_type
    msg.content_type = content_type
    msg.ai_model = ai_model
    msg.ai_temperature = ai_temperature
    msg.ai_max_tokens = ai_max_tokens
    msg.ai_output_format = ai_output_format
    msg.transform_location = transform_location
    msg.query_id = "query-1"
    msg.variables = {}
    msg.branch_name = "main"
    msg.timeout = 60
    msg.commit = "abc123"
    msg.artifact_name = "test-artifact"
    msg.artifact_definition = "def-1"
    msg.artifact_definition_name = "test-def"
    msg.target_id = "target-1"
    msg.target_kind = "TestTarget"
    msg.convert_query_response = False
    msg.context = MagicMock()
    msg.context.to_request_context.return_value = MagicMock()
    return msg


def _make_artifact(*, checksum: str = "old-checksum", storage_id: str = "old-storage") -> MagicMock:
    artifact = MagicMock()
    artifact.id = "artifact-1"
    artifact.checksum = MagicMock()
    artifact.checksum.value = checksum
    artifact.storage_id = MagicMock()
    artifact.storage_id.value = storage_id
    artifact.content_type = MagicMock()
    artifact.status = MagicMock()
    artifact.name = MagicMock()
    artifact.name.value = "test-artifact"
    artifact.save = AsyncMock()
    return artifact


def _make_integrator(ai_result: dict[str, Any] | None = None, upload_id: str = "new-storage") -> MagicMock:
    integrator = MagicMock(spec=InfrahubRepositoryIntegrator)
    integrator.render_artifact = InfrahubRepositoryIntegrator.render_artifact.__get__(
        integrator, InfrahubRepositoryIntegrator
    )

    # Mock SDK
    integrator.sdk = MagicMock()
    integrator.sdk.query_gql_query = AsyncMock(return_value={"data": {}})
    integrator.sdk.object_store = MagicMock()
    integrator.sdk.object_store.upload = AsyncMock(return_value={"identifier": upload_id})

    # Mock execute_ai_transform as a task with .with_options()
    ai_task_mock = AsyncMock(return_value=ai_result or {"content": "AI generated report", "format": "markdown"})
    options_mock = MagicMock()
    options_mock.return_value = ai_task_mock
    integrator.execute_ai_transform = MagicMock()
    integrator.execute_ai_transform.with_options = options_mock

    # Mock render_jinja2_template & execute_python_transform similarly
    jinja2_task_mock = AsyncMock(return_value="jinja2 output")
    jinja2_options = MagicMock()
    jinja2_options.return_value = jinja2_task_mock
    integrator.render_jinja2_template = MagicMock()
    integrator.render_jinja2_template.with_options = jinja2_options

    python_task_mock = AsyncMock(return_value="python output")
    python_options = MagicMock()
    python_options.return_value = python_task_mock
    integrator.execute_python_transform = MagicMock()
    integrator.execute_python_transform.with_options = python_options

    return integrator


class TestRenderArtifactAI:
    @pytest.mark.anyio
    async def test_ai_transform_dispatches_and_extracts_content(self) -> None:
        ai_content = "# Generated Report\nSome content"
        integrator = _make_integrator(ai_result={"content": ai_content, "format": "markdown"})
        artifact = _make_artifact()
        message = _make_message()

        with (
            patch("infrahub.git.integrator.registry") as mock_registry,
            patch("infrahub.git.integrator.get_event_service", new_callable=AsyncMock),
            patch("infrahub.git.integrator.ArtifactCreatedEvent"),
            patch("infrahub.git.integrator.ArtifactUpdatedEvent"),
            patch("infrahub.git.integrator.EventMeta"),
        ):
            mock_registry.get_branch_from_registry.return_value = MagicMock()
            result = await integrator.render_artifact(artifact=artifact, artifact_created=True, message=message)

        assert isinstance(result, ArtifactGenerateResult)
        assert result.changed is True
        assert result.artifact_id == "artifact-1"

        # Verify AI transform was called with correct params
        integrator.execute_ai_transform.with_options.assert_called_once_with(timeout_seconds=60)

    @pytest.mark.anyio
    async def test_ai_transform_unchanged_checksum_skips_upload(self) -> None:
        ai_content = "unchanged content"
        checksum = hashlib.md5(ai_content.encode(), usedforsecurity=False).hexdigest()

        integrator = _make_integrator(ai_result={"content": ai_content, "format": "markdown"})
        artifact = _make_artifact(checksum=checksum, storage_id="existing-storage")
        message = _make_message()

        with patch("infrahub.git.integrator.registry") as mock_registry, patch(
            "infrahub.git.integrator.get_event_service", new_callable=AsyncMock
        ):
            mock_registry.get_branch_from_registry.return_value = MagicMock()
            result = await integrator.render_artifact(artifact=artifact, artifact_created=False, message=message)

        assert result.changed is False
        assert result.storage_id == "existing-storage"
        integrator.sdk.object_store.upload.assert_not_awaited()

    @pytest.mark.anyio
    async def test_ai_transform_uses_default_model_when_none(self) -> None:
        integrator = _make_integrator()
        artifact = _make_artifact()
        message = _make_message(ai_model=None)

        with (
            patch("infrahub.git.integrator.registry") as mock_registry,
            patch("infrahub.git.integrator.get_event_service", new_callable=AsyncMock),
            patch("infrahub.git.integrator.ArtifactCreatedEvent"),
            patch("infrahub.git.integrator.ArtifactUpdatedEvent"),
            patch("infrahub.git.integrator.EventMeta"),
        ):
            mock_registry.get_branch_from_registry.return_value = MagicMock()
            await integrator.render_artifact(artifact=artifact, artifact_created=True, message=message)

        # The AI task was called — verify via the chained mock
        ai_task = integrator.execute_ai_transform.with_options.return_value
        ai_task.assert_awaited_once()
        call_kwargs = ai_task.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"

    @pytest.mark.anyio
    async def test_unsupported_transform_type_raises(self) -> None:
        integrator = _make_integrator()
        artifact = _make_artifact()
        message = _make_message(transform_type="SomeUnknownTransform")

        with patch("infrahub.git.integrator.registry") as mock_registry:
            mock_registry.get_branch_from_registry.return_value = MagicMock()
            with pytest.raises(ValueError, match="Unsupported transform type"):
                await integrator.render_artifact(artifact=artifact, artifact_created=True, message=message)
