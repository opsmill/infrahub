from __future__ import annotations

from infrahub.git.closure_builder.post_processing import MANIFEST_PATH, append_manifest_path
from infrahub.git.closure_builder.result import ClosureResult


def test_manifest_path_is_appended_to_an_empty_closure() -> None:
    """An auto-detected closure that found no other files still picks up the manifest entry.

    The manifest is a universal input to every transform in the repo, so a
    transform genuinely depending on nothing else still needs it to be
    regenerated when ``.infrahub.yml`` is edited.
    """
    original = ClosureResult(dependencies=(), complete=True, unresolved=())
    merged = append_manifest_path(result=original)
    assert merged.dependencies == (MANIFEST_PATH,)
    assert merged.complete is True


def test_manifest_path_unions_into_existing_sorted_closure() -> None:
    """The manifest path is merged into the existing closure and the result stays sorted.

    Sorted, deduplicated storage is the invariant that lets the diff layer
    skip emitting a node modification when nothing actually changed.
    """
    original = ClosureResult(
        dependencies=("templates/device.j2", "templates/partials/header.j2"),
        complete=True,
        unresolved=(),
    )
    merged = append_manifest_path(result=original)
    assert merged.dependencies == (
        ".infrahub.yml",
        "templates/device.j2",
        "templates/partials/header.j2",
    )
