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

    result = build_default_closure_builder().build(transform_config=config, worktree_root=tmp_path)

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

    result = build_default_closure_builder().build(transform_config=config, worktree_root=tmp_path)

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

    logger = logging.getLogger("test_dispatcher")
    with caplog.at_level(logging.ERROR, logger="test_dispatcher"):
        result = build_default_closure_builder(logger=logger).build(
            transform_config=config,
            worktree_root=tmp_path,
        )

    assert result.complete is False
    assert result.dependencies == ()
    assert [record.getMessage() for record in caplog.records] == [
        "Closure builder failed for transform 'missing-entry'"
    ]


def test_no_logger_is_safe(tmp_path: Path) -> None:
    """Failure isolation works without a logger - the integrator may pass None on first-call paths.

    The signature must not force callers to instantiate a logger they may not
    have at hand; a silent fallback is the documented behavior.
    """
    config = InfrahubJinja2TransformConfig(
        name="dangling",
        query="any-query",
        template_path=Path(),
    )

    result = build_default_closure_builder(logger=None).build(transform_config=config, worktree_root=tmp_path)

    assert result.complete is False
