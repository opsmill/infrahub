from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


REPO_MIRROR_KIND = "TestingRepoMirror"


@pytest.fixture
async def repo_mirror_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Agnostic schema with aware and agnostic attributes, like CoreReadOnlyRepository"""
    repo_mirror = NodeSchema(
        name="RepoMirror",
        namespace="Testing",
        branch=BranchSupportType.AGNOSTIC,
        default_filter="name__value",
        attributes=[
            AttributeSchema(
                name="name",
                kind="Text",
                unique=True,
                branch=BranchSupportType.AGNOSTIC,
            ),
            AttributeSchema(
                name="ref",
                kind="Text",
                default_value="main",
                branch=BranchSupportType.AWARE,
            ),
            AttributeSchema(
                name="commit",
                kind="Text",
                optional=True,
                branch=BranchSupportType.AWARE,
            ),
        ],
    )
    registry.schema.register_schema(schema=SchemaRoot(nodes=[repo_mirror]), branch=default_branch.name)


@pytest.fixture
async def repo_mirror_main(db: InfrahubDatabase, default_branch: Branch, repo_mirror_schema: None) -> Node:
    """A TestingRepoMirror node created on default with ref='main', commit='a'*40."""
    repo = await Node.init(db=db, schema=REPO_MIRROR_KIND, branch=default_branch)
    await repo.new(db=db, name="mirror-1", ref="main", commit="a" * 40)
    await repo.save(db=db, user_id="main-user")
    return repo
