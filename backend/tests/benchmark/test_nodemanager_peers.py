from collections.abc import Callable
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.relationship import RelationshipManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def test_account(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch) -> Node:
    node = await Node.init(db=db, schema="CoreAccount", branch=default_branch)
    await node.new(db=db, name="test_account", password="")
    await node.save(db=db)

    return node


@pytest.fixture
async def relm(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, test_account: Node
) -> RelationshipManager:
    model = registry.schema.get(name="CoreAccount")
    rel_schema = model.get_relationship("member_of_groups")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=default_branch, at=Timestamp(), node=test_account
    )

    return relm


def test_nodemanager_querypeers(
    aio_benchmark: Callable[..., Any], db: InfrahubDatabase, default_branch: Branch, test_account: Node
) -> None:
    model = registry.schema.get(name="CoreAccount")
    aio_benchmark(
        NodeManager().query_peers,
        db=db,
        ids=[test_account.id],
        source_kind=model.kind,
        schema=model.get_relationship("member_of_groups"),
        filters=[],
    )


def test_relationshipmanager_getpeer(
    aio_benchmark: Callable[..., Any], db: InfrahubDatabase, default_branch: Branch, relm: RelationshipManager
) -> None:
    aio_benchmark(relm.get_peers, db=db)
