from __future__ import annotations

from dataclasses import dataclass

import pytest
from infrahub_sdk.schema.repository import InfrahubWatchConfig

from infrahub.git.closure_builder.post_processing import MANIFEST_PATH
from infrahub.git.fingerprint.composer import (
    Jinja2TransformationFingerprintInput,
    PythonTransformationFingerprintInput,
)
from infrahub.git.fingerprint.registry import FingerprintKind, FingerprintRegistry
from tests.unit.git.fingerprint.conftest import build_composer

PY_BLOBS = {"transforms/report.py": "sha-report", MANIFEST_PATH: "sha-manifest"}
J2_BLOBS = {"templates/report.j2": "sha-template", MANIFEST_PATH: "sha-manifest"}


def _python_input(**overrides: object) -> PythonTransformationFingerprintInput:
    defaults: dict[str, object] = {
        "name": "report",
        "query_name": "q",
        "dependencies": (MANIFEST_PATH, "transforms/report.py"),
        "dependencies_complete": True,
        "watch": InfrahubWatchConfig(files=[]),
        "class_name": "Report",
        "convert_query_response": False,
    }
    defaults.update(overrides)
    return PythonTransformationFingerprintInput(**defaults)  # type: ignore[arg-type]


def _jinja2_input(**overrides: object) -> Jinja2TransformationFingerprintInput:
    defaults: dict[str, object] = {
        "name": "report",
        "query_name": "q",
        "dependencies": (MANIFEST_PATH, "templates/report.j2"),
        "dependencies_complete": True,
        "watch": InfrahubWatchConfig(files=[]),
        "template_path": "templates/report.j2",
    }
    defaults.update(overrides)
    return Jinja2TransformationFingerprintInput(**defaults)  # type: ignore[arg-type]


def _seed_query(registry: FingerprintRegistry, fingerprint: str = "query-fp") -> None:
    registry.register(kind=FingerprintKind.QUERY, name="q", fingerprint=fingerprint)


def test_python_incorporates_query_fingerprint() -> None:
    registry_a = FingerprintRegistry()
    _seed_query(registry_a, "query-fp-1")
    first = build_composer(blob_shas=PY_BLOBS, registry=registry_a).compose_transformation(_python_input())

    registry_b = FingerprintRegistry()
    _seed_query(registry_b, "query-fp-2")
    second = build_composer(blob_shas=PY_BLOBS, registry=registry_b).compose_transformation(_python_input())

    assert first != second


def test_python_changes_on_closure_blob_sha() -> None:
    registry = FingerprintRegistry()
    _seed_query(registry)
    base = build_composer(blob_shas=PY_BLOBS, registry=registry).compose_transformation(_python_input())

    registry_changed = FingerprintRegistry()
    _seed_query(registry_changed)
    changed_blobs = {**PY_BLOBS, "transforms/report.py": "sha-report-edited"}
    changed = build_composer(blob_shas=changed_blobs, registry=registry_changed).compose_transformation(_python_input())

    assert base != changed


def test_python_changes_on_class_name_and_convert_query_response() -> None:
    def digest(**overrides: object) -> str:
        registry = FingerprintRegistry()
        _seed_query(registry)
        return build_composer(blob_shas=PY_BLOBS, registry=registry).compose_transformation(_python_input(**overrides))

    base = digest()
    assert base != digest(class_name="Other")
    assert base != digest(convert_query_response=True)


def test_python_excludes_manifest_blob_from_closure() -> None:
    def digest(blobs: dict[str, str]) -> str:
        registry = FingerprintRegistry()
        _seed_query(registry)
        return build_composer(blob_shas=blobs, registry=registry).compose_transformation(_python_input())

    base = digest(PY_BLOBS)
    manifest_edited = digest({**PY_BLOBS, MANIFEST_PATH: "sha-manifest-edited"})
    assert base == manifest_edited


def test_python_folds_commit_id_only_when_watch_absent() -> None:
    def digest(*, commit: str, watch: InfrahubWatchConfig | None) -> str:
        registry = FingerprintRegistry()
        _seed_query(registry)
        return build_composer(blob_shas=PY_BLOBS, commit=commit, registry=registry).compose_transformation(
            _python_input(watch=watch)
        )

    absent_a = digest(commit="commit-1", watch=None)
    absent_b = digest(commit="commit-2", watch=None)
    assert absent_a != absent_b

    present_a = digest(commit="commit-1", watch=InfrahubWatchConfig(files=[]))
    present_b = digest(commit="commit-2", watch=InfrahubWatchConfig(files=[]))
    assert present_a == present_b


def test_python_incomplete_closure_folds_commit_id_despite_present_watch() -> None:
    def digest(*, commit: str) -> str:
        registry = FingerprintRegistry()
        _seed_query(registry)
        return build_composer(blob_shas=PY_BLOBS, commit=commit, registry=registry).compose_transformation(
            _python_input(watch=InfrahubWatchConfig(files=[]), dependencies_complete=False)
        )

    # An incomplete closure must not yield a stable fingerprint even when watch is declared.
    assert digest(commit="commit-1") != digest(commit="commit-2")


def test_missing_query_fingerprint_folds_commit_id_despite_present_watch() -> None:
    def digest(*, commit: str) -> str:
        # No query is registered, so the upstream fingerprint is unresolved.
        registry = FingerprintRegistry()
        return build_composer(blob_shas=PY_BLOBS, commit=commit, registry=registry).compose_transformation(
            _python_input(watch=InfrahubWatchConfig(files=[]))
        )

    # An unresolved upstream must not yield a stable fingerprint over an input it could not read.
    assert digest(commit="commit-1") != digest(commit="commit-2")


def test_jinja2_changes_on_template_path_and_closure() -> None:
    def digest(*, blobs: dict[str, str], **overrides: object) -> str:
        registry = FingerprintRegistry()
        _seed_query(registry)
        return build_composer(blob_shas=blobs, registry=registry).compose_transformation(_jinja2_input(**overrides))

    base = digest(blobs=J2_BLOBS)
    assert base != digest(blobs=J2_BLOBS, template_path="templates/other.j2")
    assert base != digest(blobs={**J2_BLOBS, "templates/report.j2": "sha-template-edited"})


def test_jinja2_excludes_manifest_blob_from_closure() -> None:
    def digest(blobs: dict[str, str]) -> str:
        registry = FingerprintRegistry()
        _seed_query(registry)
        return build_composer(blob_shas=blobs, registry=registry).compose_transformation(_jinja2_input())

    assert digest(J2_BLOBS) == digest({**J2_BLOBS, MANIFEST_PATH: "sha-manifest-edited"})


@dataclass
class Jinja2CommitFoldCase:
    name: str
    watch: InfrahubWatchConfig | None
    dependencies_complete: bool
    seed_query: bool
    stable: bool


JINJA2_COMMIT_FOLD_CASES = [
    Jinja2CommitFoldCase(
        name="complete_closure_without_watch_is_stable",
        watch=None,
        dependencies_complete=True,
        seed_query=True,
        stable=True,
    ),
    Jinja2CommitFoldCase(
        name="complete_closure_with_empty_watch_is_stable",
        watch=InfrahubWatchConfig(files=[]),
        dependencies_complete=True,
        seed_query=True,
        stable=True,
    ),
    Jinja2CommitFoldCase(
        name="incomplete_closure_without_watch_folds_commit_id",
        watch=None,
        dependencies_complete=False,
        seed_query=True,
        stable=False,
    ),
    Jinja2CommitFoldCase(
        name="unresolved_query_folds_commit_id_despite_complete_closure",
        watch=None,
        dependencies_complete=True,
        seed_query=False,
        stable=False,
    ),
]


@pytest.mark.parametrize("case", JINJA2_COMMIT_FOLD_CASES, ids=lambda case: case.name)
def test_jinja2_commit_id_folding(case: Jinja2CommitFoldCase) -> None:
    # A Jinja2 transform's dependency list is parsed out of the template, so a complete one is
    # trusted on its own: the fingerprint stays the same across unrelated commits with no watch
    # declared. If a reference could not be followed, or the query the transform reads was never
    # fingerprinted, the commit id goes back in and the fingerprint changes on every commit.
    def digest(*, commit: str) -> str:
        registry = FingerprintRegistry()
        if case.seed_query:
            _seed_query(registry)
        return build_composer(blob_shas=J2_BLOBS, commit=commit, registry=registry).compose_transformation(
            _jinja2_input(watch=case.watch, dependencies_complete=case.dependencies_complete)
        )

    first = digest(commit="commit-1")
    second = digest(commit="commit-2")
    assert (first == second) is case.stable
