from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.workflows.utils import merge_tags, render_tags


@dataclass
class RenderTagsTestCase:
    name: str
    branches: list[str] | None
    nodes: list[str] | None
    others: list[str] | None
    namespace: bool
    db_change: bool
    expected: set[str]


RENDER_TAGS_TEST_CASES = [
    RenderTagsTestCase(
        name="branch_and_node_with_namespace",
        branches=["main"],
        nodes=["node-1"],
        others=None,
        namespace=True,
        db_change=False,
        expected={"infrahub.app/branch/main", "infrahub.app/node/node-1", "infrahub.app"},
    ),
    RenderTagsTestCase(
        name="global_branch_is_not_tagged",
        branches=[GLOBAL_BRANCH_NAME, "branch2"],
        nodes=None,
        others=None,
        namespace=False,
        db_change=False,
        expected={"infrahub.app/branch/branch2"},
    ),
    RenderTagsTestCase(
        name="others_and_database_change",
        branches=None,
        nodes=None,
        others=["custom"],
        namespace=False,
        db_change=True,
        expected={"custom", "infrahub.app/database-change"},
    ),
]


@pytest.mark.parametrize("case", RENDER_TAGS_TEST_CASES, ids=lambda case: case.name)
def test_render_tags(case: RenderTagsTestCase) -> None:
    tags = render_tags(
        branches=case.branches,
        nodes=case.nodes,
        others=case.others,
        namespace=case.namespace,
        db_change=case.db_change,
    )

    assert tags == case.expected


def test_merge_tags_returns_none_when_every_tag_is_present() -> None:
    assert merge_tags(current=["infrahub.app/branch/main", "other"], tags={"infrahub.app/branch/main"}) is None


def test_merge_tags_returns_the_union_when_a_tag_is_missing() -> None:
    merged = merge_tags(current=["other", "infrahub.app/branch/main"], tags={"infrahub.app/node/node-1"})

    assert merged == ["infrahub.app/branch/main", "infrahub.app/node/node-1", "other"]
