from __future__ import annotations

from infrahub.git.closure_builder.post_processing import MANIFEST_PATH
from infrahub.git.fingerprint.composer import ClosurePathSelector


def _selector() -> ClosurePathSelector:
    return ClosurePathSelector(excluded_paths=frozenset({MANIFEST_PATH}))


def test_manifest_path_is_excluded() -> None:
    selected = _selector().select([MANIFEST_PATH, "transforms/report.py"])
    assert selected == ["transforms/report.py"]


def test_own_source_and_watch_files_are_retained() -> None:
    dependencies = [MANIFEST_PATH, "transforms/report.py", "shared/helpers.py", "templates/report.j2"]
    selected = _selector().select(dependencies)
    assert selected == ["transforms/report.py", "shared/helpers.py", "templates/report.j2"]


def test_selection_without_manifest_is_unchanged() -> None:
    dependencies = ["transforms/report.py", "shared/helpers.py"]
    assert _selector().select(dependencies) == dependencies
