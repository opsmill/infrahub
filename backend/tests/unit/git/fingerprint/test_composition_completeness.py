"""Guard that every field of a repository manifest entry is accounted for in its fingerprint.

The fingerprint is the signal that a definition's inputs changed. An output-affecting manifest
field that never reaches the composition is a silent under-regeneration: the definition renders
differently and nothing notices. These tests pin the classification of every manifest field, so
adding a field to a repository config model fails here until it is either folded in or recorded
as not affecting the output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.schema.repository import (
    InfrahubGeneratorDefinitionConfig,
    InfrahubJinja2TransformConfig,
    InfrahubPythonTransformConfig,
    InfrahubRepositoryArtifactDefinitionConfig,
    InfrahubWatchConfig,
)

from infrahub.git.fingerprint.composer import (
    ArtifactDefinitionFingerprintInput,
    GeneratorDefinitionFingerprintInput,
    Jinja2TransformationFingerprintInput,
    PythonTransformationFingerprintInput,
)
from infrahub.git.fingerprint.registry import FingerprintKind, FingerprintRegistry
from tests.unit.git.fingerprint.conftest import build_composer

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import BaseModel

QUERY_NAME = "q"
TRANSFORMATION_NAME = "report"
UPSTREAM_FINGERPRINT = "upstream-fp"

BLOBS = {
    "transforms/report.py": "sha-report",
    "templates/report.j2": "sha-template",
    "generators/tags.py": "sha-gen",
}

# Editing `watch` changes which files the stored closure names, which is how it reaches the
# fingerprint. Every kind is exercised through the same extra closure entry.
WIDER_CLOSURE = {"dependencies": ("shared/helpers.py",)}


def _seed_upstream(registry: FingerprintRegistry, *, kind: FingerprintKind, name: str, fingerprint: str) -> None:
    registry.register(kind=kind, name=name, fingerprint=fingerprint)


def _jinja2_digest(**overrides: Any) -> str:
    registry = FingerprintRegistry()
    _seed_upstream(
        registry,
        kind=FingerprintKind.QUERY,
        name=QUERY_NAME,
        fingerprint=overrides.pop("query_fingerprint", UPSTREAM_FINGERPRINT),
    )
    inputs: dict[str, Any] = {
        "name": TRANSFORMATION_NAME,
        "query_name": QUERY_NAME,
        "dependencies": ("templates/report.j2",),
        "dependencies_complete": True,
        "watch": InfrahubWatchConfig(files=[]),
        "template_path": "templates/report.j2",
    }
    inputs.update(overrides)
    return build_composer(blob_shas=BLOBS, registry=registry).compose_transformation(
        Jinja2TransformationFingerprintInput(**inputs)
    )


def _python_digest(**overrides: Any) -> str:
    registry = FingerprintRegistry()
    _seed_upstream(
        registry,
        kind=FingerprintKind.QUERY,
        name=QUERY_NAME,
        fingerprint=overrides.pop("query_fingerprint", UPSTREAM_FINGERPRINT),
    )
    inputs: dict[str, Any] = {
        "name": TRANSFORMATION_NAME,
        "query_name": QUERY_NAME,
        "dependencies": ("transforms/report.py",),
        "dependencies_complete": True,
        "watch": InfrahubWatchConfig(files=[]),
        "file_path": "transforms/report.py",
        "class_name": "Report",
        "convert_query_response": False,
    }
    inputs.update(overrides)
    return build_composer(blob_shas=BLOBS, registry=registry).compose_transformation(
        PythonTransformationFingerprintInput(**inputs)
    )


def _generator_digest(**overrides: Any) -> str:
    registry = FingerprintRegistry()
    _seed_upstream(
        registry,
        kind=FingerprintKind.QUERY,
        name=QUERY_NAME,
        fingerprint=overrides.pop("query_fingerprint", UPSTREAM_FINGERPRINT),
    )
    inputs: dict[str, Any] = {
        "name": "tags",
        "query_name": QUERY_NAME,
        "dependencies": ("generators/tags.py",),
        "dependencies_complete": True,
        "watch": InfrahubWatchConfig(files=[]),
        "parameters": {"name": "name__value"},
        "file_path": "generators/tags.py",
        "class_name": "Generator",
        "convert_query_response": False,
        "target_group_id": "group-1",
    }
    inputs.update(overrides)
    return build_composer(blob_shas=BLOBS, registry=registry).compose_generator_definition(
        GeneratorDefinitionFingerprintInput(**inputs)
    )


def _artifact_digest(**overrides: Any) -> str:
    registry = FingerprintRegistry()
    _seed_upstream(
        registry,
        kind=FingerprintKind.TRANSFORMATION,
        name=TRANSFORMATION_NAME,
        fingerprint=overrides.pop("transformation_fingerprint", UPSTREAM_FINGERPRINT),
    )
    inputs: dict[str, Any] = {
        "name": "device-config",
        "transformation_name": TRANSFORMATION_NAME,
        "parameters": {"name": "name__value"},
        "content_type": "text/plain",
        "artifact_name": "device-config",
        "target_group_id": "group-1",
    }
    inputs.update(overrides)
    return build_composer(blob_shas=BLOBS, registry=registry).compose_artifact_definition(
        ArtifactDefinitionFingerprintInput(**inputs)
    )


@dataclass(frozen=True, kw_only=True)
class FoldedField:
    manifest_field: str
    """Name of the field on the repository config model."""

    input_override: dict[str, Any]
    """The fingerprint-input change that editing this manifest field produces."""


@dataclass(frozen=True, kw_only=True)
class DefinitionKind:
    name: str
    """Test id, and the wording used when a field is unclassified."""

    config_model: type[BaseModel]
    """The manifest entry model whose fields must all be accounted for."""

    digest: Callable[..., str]

    folded: tuple[FoldedField, ...]

    excluded: dict[str, str] = field(default_factory=dict)
    """Fields deliberately left out, mapped to the reason they cannot change the output."""


NOT_AN_INPUT = "definition identity, not an input: a rename replaces the node"
NOT_RENDERED = "never read while producing the output"
RUN_SCHEDULING = "decides when the definition runs, not what it produces"

DEFINITION_KINDS = [
    DefinitionKind(
        name="jinja2_transform",
        config_model=InfrahubJinja2TransformConfig,
        digest=_jinja2_digest,
        folded=(
            FoldedField(manifest_field="query", input_override={"query_fingerprint": "other-fp"}),
            FoldedField(manifest_field="template_path", input_override={"template_path": "templates/other.j2"}),
            FoldedField(manifest_field="watch", input_override=WIDER_CLOSURE),
        ),
        excluded={"name": NOT_AN_INPUT, "description": NOT_RENDERED},
    ),
    DefinitionKind(
        name="python_transform",
        config_model=InfrahubPythonTransformConfig,
        digest=_python_digest,
        folded=(
            FoldedField(manifest_field="file_path", input_override={"file_path": "transforms/other.py"}),
            FoldedField(manifest_field="class_name", input_override={"class_name": "Other"}),
            FoldedField(manifest_field="convert_query_response", input_override={"convert_query_response": True}),
            FoldedField(manifest_field="watch", input_override=WIDER_CLOSURE),
        ),
        excluded={"name": NOT_AN_INPUT, "description": NOT_RENDERED},
    ),
    DefinitionKind(
        name="generator_definition",
        config_model=InfrahubGeneratorDefinitionConfig,
        digest=_generator_digest,
        folded=(
            FoldedField(manifest_field="query", input_override={"query_fingerprint": "other-fp"}),
            FoldedField(manifest_field="file_path", input_override={"file_path": "generators/other.py"}),
            FoldedField(manifest_field="class_name", input_override={"class_name": "Other"}),
            FoldedField(manifest_field="convert_query_response", input_override={"convert_query_response": True}),
            FoldedField(manifest_field="parameters", input_override={"parameters": {"name": "other__value"}}),
            FoldedField(manifest_field="targets", input_override={"target_group_id": "group-2"}),
            FoldedField(manifest_field="watch", input_override=WIDER_CLOSURE),
        ),
        excluded={
            "name": NOT_AN_INPUT,
            "execute_in_proposed_change": RUN_SCHEDULING,
            "execute_after_merge": RUN_SCHEDULING,
        },
    ),
    DefinitionKind(
        name="artifact_definition",
        config_model=InfrahubRepositoryArtifactDefinitionConfig,
        digest=_artifact_digest,
        folded=(
            FoldedField(manifest_field="transformation", input_override={"transformation_fingerprint": "other-fp"}),
            FoldedField(manifest_field="parameters", input_override={"parameters": {"name": "other__value"}}),
            FoldedField(manifest_field="content_type", input_override={"content_type": "application/json"}),
            FoldedField(manifest_field="artifact_name", input_override={"artifact_name": "other-name"}),
            FoldedField(manifest_field="targets", input_override={"target_group_id": "group-2"}),
        ),
        excluded={"name": NOT_AN_INPUT},
    ),
]


@pytest.mark.parametrize("kind", DEFINITION_KINDS, ids=lambda kind: kind.name)
def test_every_manifest_field_is_classified(kind: DefinitionKind) -> None:
    """Each field of the manifest entry is either folded into the fingerprint or excluded with a reason."""
    classified = {folded.manifest_field for folded in kind.folded} | set(kind.excluded)
    assert classified == set(kind.config_model.model_fields)


@pytest.mark.parametrize("kind", DEFINITION_KINDS, ids=lambda kind: kind.name)
def test_folded_manifest_fields_move_the_fingerprint(kind: DefinitionKind) -> None:
    """Editing any field classified as folded produces a different fingerprint."""
    base = kind.digest()
    unmoved = [folded.manifest_field for folded in kind.folded if kind.digest(**folded.input_override) == base]
    assert unmoved == []
