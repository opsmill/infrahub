from __future__ import annotations

from infrahub_sdk.schema.repository import InfrahubWatchConfig

from infrahub.git.fingerprint.composer import GeneratorDefinitionFingerprintInput
from infrahub.git.fingerprint.registry import FingerprintKind, FingerprintRegistry
from tests.unit.git.fingerprint.conftest import build_composer

BLOBS = {"generators/tags.py": "sha-gen"}


def _input(**overrides: object) -> GeneratorDefinitionFingerprintInput:
    defaults: dict[str, object] = {
        "name": "tags",
        "query_name": "q",
        "dependencies": ("generators/tags.py",),
        "dependencies_complete": True,
        "watch": InfrahubWatchConfig(files=[]),
        "parameters": {"name": "name__value"},
        "file_path": "generators/tags.py",
        "class_name": "Generator",
        "convert_query_response": False,
        "target_group_id": "group-1",
    }
    defaults.update(overrides)
    return GeneratorDefinitionFingerprintInput(**defaults)  # type: ignore[arg-type]


def _digest(
    *,
    query_fingerprint: str = "query-fp",
    commit: str = "commit-1",
    blobs: dict[str, str] | None = None,
    **overrides: object,
) -> str:
    registry = FingerprintRegistry()
    registry.register(kind=FingerprintKind.QUERY, name="q", fingerprint=query_fingerprint)
    composer = build_composer(blob_shas=blobs or BLOBS, commit=commit, registry=registry)
    return composer.compose_generator_definition(_input(**overrides))


def test_incorporates_query_fingerprint_and_closure() -> None:
    base = _digest()
    assert base != _digest(query_fingerprint="other")
    assert base != _digest(blobs={**BLOBS, "generators/tags.py": "sha-gen-edited"})


def test_changes_on_parameters_class_name_convert_and_group() -> None:
    base = _digest()
    assert base != _digest(parameters={"name": "other"})
    assert base != _digest(class_name="Other")
    assert base != _digest(convert_query_response=True)
    assert base != _digest(target_group_id="group-2")


def test_changes_on_file_path_within_an_unchanged_closure() -> None:
    """Moving the entry point between two files already in the closure moves the fingerprint.

    A generator whose `watch` names its directory carries every file in that directory, so
    repointing `file_path` at a sibling leaves the closure and every blob sha identical.
    """
    blobs = {**BLOBS, "generators/sibling.py": "sha-sibling"}
    closure = ("generators/sibling.py", "generators/tags.py")

    base = _digest(blobs=blobs, dependencies=closure, file_path="generators/tags.py")
    repointed = _digest(blobs=blobs, dependencies=closure, file_path="generators/sibling.py")
    assert base != repointed


def test_folds_commit_id_only_when_watch_absent() -> None:
    assert _digest(commit="commit-1", watch=None) != _digest(commit="commit-2", watch=None)
    assert _digest(commit="commit-1", watch=InfrahubWatchConfig(files=[])) == _digest(
        commit="commit-2", watch=InfrahubWatchConfig(files=[])
    )


def test_incomplete_closure_folds_commit_id_despite_present_watch() -> None:
    watch = InfrahubWatchConfig(files=[])
    unstable_1 = _digest(commit="commit-1", watch=watch, dependencies_complete=False)
    unstable_2 = _digest(commit="commit-2", watch=watch, dependencies_complete=False)
    assert unstable_1 != unstable_2


def test_hashes_a_declared_manifest_entry_like_any_other_file() -> None:
    """A closure carrying `.infrahub.yml` is only carrying it because `watch` named it.

    Nothing merges the manifest in on its own any more, so it gets no special treatment:
    its blob is hashed and an edit to it moves the fingerprint.
    """
    closure = (".infrahub.yml", "generators/tags.py")
    blobs = {**BLOBS, ".infrahub.yml": "sha-manifest"}

    base = _digest(blobs=blobs, dependencies=closure)
    manifest_edited = _digest(blobs={**blobs, ".infrahub.yml": "sha-manifest-edited"}, dependencies=closure)
    assert base != manifest_edited
