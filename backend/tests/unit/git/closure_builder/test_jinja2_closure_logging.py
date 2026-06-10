from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from infrahub_sdk.schema.repository import InfrahubJinja2TransformConfig

from infrahub.git.closure_builder.jinja2_closure import Jinja2Closure
from infrahub.git.closure_builder.jinja2_reference_resolver import Jinja2ReferenceResolver

if TYPE_CHECKING:
    import pytest

LOGGER = logging.getLogger(__name__)


def _write(root: Path, rel: str, content: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_each_unresolved_reference_in_one_template_is_logged(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Every unresolved reference in a single template is reported, not just the first.

    A template can defeat static analysis at several sites at once; the walker must
    surface all of them so an operator can size a covering ``watch.files`` list
    rather than discovering the missed sites one regeneration at a time.
    """
    _write(
        tmp_path,
        "templates/device.j2",
        "{% include dynamic_one %}\n{% include dynamic_two %}\n",
    )
    config = InfrahubJinja2TransformConfig(
        name="device",
        query="any-query",
        template_path=Path("templates/device.j2"),
    )

    closure = Jinja2Closure(reference_resolver=Jinja2ReferenceResolver(), logger=LOGGER)
    with caplog.at_level(logging.INFO, logger=LOGGER.name):
        result = closure.build(transform_config=config, worktree_root=tmp_path)

    assert result.complete is False
    assert len(result.unresolved) == 2
    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "Closure builder for transform 'device' encountered unresolved reference "
        "in templates/device.j2: dynamic include/import/extends; dependencies_complete=False.",
        "Closure builder for transform 'device' encountered unresolved reference "
        "in templates/device.j2: dynamic include/import/extends; dependencies_complete=False.",
    ]


def test_a_complete_closure_logs_nothing(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A template whose references all resolve produces no unresolved-reference log noise."""
    _write(tmp_path, "templates/device.j2", "{% include 'partials/header.j2' %}\nbody\n")
    _write(tmp_path, "partials/header.j2", "header\n")
    config = InfrahubJinja2TransformConfig(
        name="device",
        query="any-query",
        template_path=Path("templates/device.j2"),
    )

    closure = Jinja2Closure(reference_resolver=Jinja2ReferenceResolver(), logger=LOGGER)
    with caplog.at_level(logging.INFO, logger=LOGGER.name):
        result = closure.build(transform_config=config, worktree_root=tmp_path)

    assert result.complete is True
    assert caplog.records == []
