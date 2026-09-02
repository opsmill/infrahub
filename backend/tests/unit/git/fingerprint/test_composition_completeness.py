"""Guard that every field of a repository manifest entry is accounted for in its fingerprint.

The fingerprint is the signal that a definition's inputs changed. An output-affecting manifest
field that never reaches the composition is a silent under-regeneration: the definition renders
differently and nothing notices. These tests pin the classification of every manifest field, so
adding a field to a repository config model fails here until it is either folded in or recorded
as not affecting the output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from git import Repo
from infrahub_sdk.schema.repository import (
    InfrahubGeneratorDefinitionConfig,
    InfrahubJinja2TransformConfig,
    InfrahubPythonTransformConfig,
    InfrahubRepositoryArtifactDefinitionConfig,
    InfrahubWatchConfig,
)

from infrahub.git.closure_builder.dispatcher import build_default_closure_builder
from infrahub.git.fingerprint.composer import (
    ArtifactDefinitionFingerprintInput,
    FingerprintComposer,
    GeneratorDefinitionFingerprintInput,
    Jinja2TransformationFingerprintInput,
    PythonTransformationFingerprintInput,
    QueryFingerprintInput,
    build_fingerprint_composer,
)
from infrahub.git.fingerprint.registry import FingerprintKind, FingerprintRegistry
from tests.unit.git.fingerprint.conftest import build_composer

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import BaseModel

    from infrahub.git.closure_builder.result import ClosureResult

QUERY_NAME = "q"
TRANSFORMATION_NAME = "report"
UPSTREAM_FINGERPRINT = "upstream-fp"

BLOBS = {
    "transforms/report.py": "sha-report",
    "templates/report.j2": "sha-template",
    "generators/tags.py": "sha-gen",
}

# `watch` never becomes a fingerprint term of its own: it reaches the digest only through the
# closure the builder derives from it. Substituting a `dependencies` edit here would assert
# nothing about that derivation, so the field is proven end to end further down instead.
DELEGATED_FIELDS = frozenset({"watch"})


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

    input_override: dict[str, Any] | None
    """The fingerprint-input change that editing this manifest field produces.

    None when the field reaches the digest only indirectly and a dedicated end-to-end test
    proves it, rather than a direct substitution that would beg the question.
    """


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
            FoldedField(manifest_field="watch", input_override=None),
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
            FoldedField(manifest_field="watch", input_override=None),
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
            FoldedField(manifest_field="watch", input_override=None),
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
    unmoved = [
        folded.manifest_field
        for folded in kind.folded
        if folded.input_override is not None and kind.digest(**folded.input_override) == base
    ]
    assert unmoved == []


@pytest.mark.parametrize("kind", DEFINITION_KINDS, ids=lambda kind: kind.name)
def test_only_known_fields_delegate_their_proof(kind: DefinitionKind) -> None:
    """A field may skip the digest check above only if it is on the delegated list.

    Marking a field delegated has to be a visible edit to `DELEGATED_FIELDS`, so a future
    change cannot quietly opt a field out of being proven at all.
    """
    delegated = {folded.manifest_field for folded in kind.folded if folded.input_override is None}
    assert delegated == DELEGATED_FIELDS & set(kind.config_model.model_fields)


@dataclass(frozen=True, kw_only=True)
class WatchChainCase:
    name: str

    entry: str
    """Repo-relative path of the definition's entry point."""

    undeclared: str
    """A tracked file that only a `watch.files` entry can bring into the closure."""

    build_config: Callable[[InfrahubWatchConfig], Any]
    """Build the manifest config for this kind with the given watch declaration."""

    compose: Callable[[FingerprintComposer, ClosureResult, InfrahubWatchConfig], str]


def _python_config(watch: InfrahubWatchConfig) -> InfrahubPythonTransformConfig:
    return InfrahubPythonTransformConfig(
        name=TRANSFORMATION_NAME, file_path=Path("transforms/report.py"), class_name="Report", watch=watch
    )


def _jinja2_config(watch: InfrahubWatchConfig) -> InfrahubJinja2TransformConfig:
    return InfrahubJinja2TransformConfig(
        name=TRANSFORMATION_NAME, query=QUERY_NAME, template_path=Path("templates/report.j2"), watch=watch
    )


def _generator_config(watch: InfrahubWatchConfig) -> InfrahubGeneratorDefinitionConfig:
    return InfrahubGeneratorDefinitionConfig(
        name="tags", file_path=Path("generators/tags.py"), query=QUERY_NAME, targets="tags-group", watch=watch
    )


def _compose_python_from_closure(
    composer: FingerprintComposer, closure: ClosureResult, watch: InfrahubWatchConfig
) -> str:
    return composer.compose_transformation(
        PythonTransformationFingerprintInput(
            name=TRANSFORMATION_NAME,
            query_name=QUERY_NAME,
            dependencies=closure.dependencies,
            dependencies_complete=closure.complete,
            watch=watch,
            file_path="transforms/report.py",
            class_name="Report",
            convert_query_response=False,
        )
    )


def _compose_jinja2_from_closure(
    composer: FingerprintComposer, closure: ClosureResult, watch: InfrahubWatchConfig
) -> str:
    return composer.compose_transformation(
        Jinja2TransformationFingerprintInput(
            name=TRANSFORMATION_NAME,
            query_name=QUERY_NAME,
            dependencies=closure.dependencies,
            dependencies_complete=closure.complete,
            watch=watch,
            template_path="templates/report.j2",
        )
    )


def _compose_generator_from_closure(
    composer: FingerprintComposer, closure: ClosureResult, watch: InfrahubWatchConfig
) -> str:
    return composer.compose_generator_definition(
        GeneratorDefinitionFingerprintInput(
            name="tags",
            query_name=QUERY_NAME,
            dependencies=closure.dependencies,
            dependencies_complete=closure.complete,
            watch=watch,
            parameters={"name": "name__value"},
            file_path="generators/tags.py",
            class_name="Generator",
            convert_query_response=False,
            target_group_id="group-1",
        )
    )


WATCH_CHAIN_CASES = [
    WatchChainCase(
        name="python_transform",
        entry="transforms/report.py",
        undeclared="transforms/helpers.py",
        build_config=_python_config,
        compose=_compose_python_from_closure,
    ),
    WatchChainCase(
        name="jinja2_transform",
        entry="templates/report.j2",
        undeclared="templates/unreferenced.j2",
        build_config=_jinja2_config,
        compose=_compose_jinja2_from_closure,
    ),
    WatchChainCase(
        name="generator_definition",
        entry="generators/tags.py",
        undeclared="generators/helpers.py",
        build_config=_generator_config,
        compose=_compose_generator_from_closure,
    ),
]

WATCH_CHAIN_FILES = [
    "transforms/report.py",
    "transforms/helpers.py",
    "templates/report.j2",
    "templates/unreferenced.j2",
    "generators/tags.py",
    "generators/helpers.py",
]


@pytest.fixture
def watch_chain_repo(tmp_path: Path) -> tuple[Path, str]:
    """A committed repository holding an entry point and an unreferenced sibling per kind."""
    repo = Repo.init(tmp_path)
    for relative in WATCH_CHAIN_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {relative}\n", encoding="utf-8")
    repo.index.add(WATCH_CHAIN_FILES)
    commit = repo.index.commit("seed")
    return tmp_path, commit.hexsha


@pytest.mark.parametrize("case", WATCH_CHAIN_CASES, ids=lambda case: case.name)
def test_watch_files_reaches_the_fingerprint_through_the_closure(
    case: WatchChainCase, watch_chain_repo: tuple[Path, str]
) -> None:
    """Declaring a file under `watch.files` widens the real closure and moves the digest.

    This runs the whole chain rather than substituting a `dependencies` edit: the closure
    builder derives the dependency list from the declaration, and the composer hashes that
    list. Both declarations are non-empty objects, so the commit-id fold is absent from each
    and the declared file is the only difference between the two digests.
    """
    worktree_root, commit = watch_chain_repo
    builder = build_default_closure_builder(logger=logging.getLogger(__name__))

    def closure_and_digest(watch: InfrahubWatchConfig) -> tuple[ClosureResult, str]:
        result = builder.build(transform_config=case.build_config(watch), worktree_root=worktree_root)
        composer = build_fingerprint_composer(repo=Repo(worktree_root), commit=commit)
        composer.compose_query(QueryFingerprintInput(name=QUERY_NAME, query_text="query { Foo { id } }"))
        return result, case.compose(composer, result, watch)

    bare_closure, bare_digest = closure_and_digest(InfrahubWatchConfig(files=[]))
    wide_closure, wide_digest = closure_and_digest(InfrahubWatchConfig(files=[case.undeclared]))

    assert case.undeclared not in bare_closure.dependencies
    assert set(wide_closure.dependencies) == {case.entry, case.undeclared}
    assert bare_digest != wide_digest
