from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.schema import SchemaRoot
from tests.component.profiles.queries.helpers import DEVICE, LABEL, RACK, SITE, Peers, create_node
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def peers(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> Peers:
    await load_schema(db=db, schema=SchemaRoot(nodes=[SITE, RACK, LABEL, DEVICE]), branch_name=default_branch.name)
    return Peers(
        sites=[
            await create_node(db=db, branch=default_branch, kind="TestSite", name=f"site-{idx}") for idx in range(2)
        ],
        racks=[
            await create_node(db=db, branch=default_branch, kind="TestRack", name=f"rack-{idx}") for idx in range(2)
        ],
        labels=[
            await create_node(db=db, branch=default_branch, kind="TestLabel", name=f"label-{idx}") for idx in range(3)
        ],
    )
