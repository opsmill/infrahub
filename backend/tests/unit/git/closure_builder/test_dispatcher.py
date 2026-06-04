from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from git import Repo
from infrahub_sdk.schema.repository import (
    InfrahubJinja2TransformConfig,
    InfrahubPythonTransformConfig,
)

from infrahub.git.closure_builder.dispatcher import build_default_closure_builder

if TYPE_CHECKING:
    import pytest

LOGGER = logging.getLogger(__name__)


def _write(root: Path, rel: str, content: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_jinja2_config_dispatches_to_jinja2_closure(tmp_path: Path) -> None:
    """A Jinja2 transform config is dispatched to the Jinja2 builder and the manifest path is appended.

    The dispatcher is the single integration boundary between the per-language
    builders and the integrator, so this checks both dispatch correctness and
    the post-processing step in one place.
    """
    _write(tmp_path, "templates/device.j2", "static body\n")

    config = InfrahubJinja2TransformConfig(
        name="device",
        query="any-query",
        template_path=Path("templates/device.j2"),
    )

    result = build_default_closure_builder(logger=LOGGER).build(transform_config=config, worktree_root=tmp_path)

    assert "templates/device.j2" in result.dependencies
    assert ".infrahub.yml" in result.dependencies
    assert result.complete is True


def test_python_config_dispatches_to_python_closure(tmp_path: Path) -> None:
    """A Python transform config is dispatched to the Python builder and the manifest path is appended."""
    repo = Repo.init(tmp_path)
    _write(tmp_path, "transforms/network/main.py", "")
    _write(tmp_path, "transforms/network/helpers.py", "")
    repo.index.add(["transforms/network/main.py", "transforms/network/helpers.py"])
    repo.index.commit("seed")

    config = InfrahubPythonTransformConfig(
        name="net",
        file_path=Path("transforms/network/main.py"),
    )

    result = build_default_closure_builder(logger=LOGGER).build(transform_config=config, worktree_root=tmp_path)

    assert "transforms/network/main.py" in result.dependencies
    assert "transforms/network/helpers.py" in result.dependencies
    assert ".infrahub.yml" in result.dependencies
    assert result.complete is True


def test_jinja2_failure_is_isolated_and_logged(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A Jinja2 builder failure produces a fallback result and an error log; the import flow can continue.

    Failure isolation is the contract that lets the integrator import the
    rest of the repository's transforms when a single transform's source is
    broken or its closure cannot be computed for a documented reason.
    """
    config = InfrahubJinja2TransformConfig(
        name="missing-entry",
        query="any-query",
        template_path=Path(),
    )

    with caplog.at_level(logging.ERROR, logger=LOGGER.name):
        result = build_default_closure_builder(logger=LOGGER).build(
            transform_config=config,
            worktree_root=tmp_path,
        )

    assert result.complete is False
    assert result.dependencies == ()
    assert [record.getMessage() for record in caplog.records] == [
        "Closure builder failed for transform 'missing-entry'"
    ]


def test_closure_failure_does_not_poison_well_formed_siblings(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A broken transform falls back to an incomplete closure without affecting a sibling's.

    The integrator builds each transform's closure with its own ``build`` call, so a
    single transform whose source cannot be analyzed must yield an incomplete fallback
    and an error log while the rest of the repository's transforms still produce fully
    populated closures - the regression guard behind the safe per-transform rollout.
    """
    _write(tmp_path, "templates/device.j2", "static body\n")
    builder = build_default_closure_builder(logger=LOGGER)

    broken = InfrahubJinja2TransformConfig(name="broken", query="any-query", template_path=Path())
    healthy = InfrahubJinja2TransformConfig(
        name="healthy", query="any-query", template_path=Path("templates/device.j2")
    )

    with caplog.at_level(logging.ERROR, logger=LOGGER.name):
        broken_result = builder.build(transform_config=broken, worktree_root=tmp_path)
        healthy_result = builder.build(transform_config=healthy, worktree_root=tmp_path)

    assert broken_result.complete is False
    assert broken_result.dependencies == ()
    assert healthy_result.complete is True
    assert "templates/device.j2" in healthy_result.dependencies
    assert [record.getMessage() for record in caplog.records] == ["Closure builder failed for transform 'broken'"]
