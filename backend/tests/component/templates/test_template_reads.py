from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.registry import registry
from tests.constants import TestKind
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.schema import DEVICE_SCHEMA, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def device_schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=DEVICE_SCHEMA, branch_name=default_branch.name)


async def _build_template(db: InfrahubDatabase, branch: Branch, name: str, nbr_interfaces: int) -> Node:
    template = await Node.init(db=db, schema=f"Template{TestKind.DEVICE}", branch=branch)
    await template.new(db=db, template_name=name, manufacturer="Acme", weight=1, airflow="Passive")
    await template.save(db=db)

    for idx in range(nbr_interfaces):
        interface = await Node.init(db=db, schema=f"Template{TestKind.PHYSICAL_INTERFACE}", branch=branch)
        await interface.new(
            db=db,
            template_name=f"{name}-eth{idx}",
            name=f"eth{idx}",
            phys_type="SFP+ (10GE)",
            device=template.id,
        )
        await interface.save(db=db)

    return template


async def test_create_from_template_does_not_read_its_empty_relationships(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None
) -> None:
    """A template is read with its relationships, so the ones it leaves empty cost no query."""
    template = await _build_template(db=db, branch=default_branch, name="empty-template", nbr_interfaces=0)
    device_schema_obj = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
    counting_db = CountingInfrahubDatabase.from_db(db=db)

    device = await create_node(
        data={"name": "from-empty-template", "object_template": {"id": template.id}},
        db=counting_db,
        branch=default_branch,
        schema=device_schema_obj,
    )

    assert device.manufacturer.value == "Acme"
    assert device.weight.value == 1
    # The only remaining read looks for the component peers the new node has to be given.
    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 1


async def test_create_from_template_reads_the_component_peers_in_one_query(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None
) -> None:
    """The peers of a component relationship are read with their own relationships, all at once."""
    device_schema_obj = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
    counts = {}

    for nbr_interfaces in (1, 5):
        template = await _build_template(
            db=db, branch=default_branch, name=f"template-{nbr_interfaces}", nbr_interfaces=nbr_interfaces
        )
        counting_db = CountingInfrahubDatabase.from_db(db=db)

        device = await create_node(
            data={"name": f"device-{nbr_interfaces}", "object_template": {"id": template.id}},
            db=counting_db,
            branch=default_branch,
            schema=device_schema_obj,
        )

        reloaded = await NodeManager.get_one(db=db, id=device.id, branch=default_branch, raise_on_error=True)
        interfaces = await reloaded.interfaces.get_peers(db=db)
        assert len(interfaces) == nbr_interfaces
        assert {interface.name.value for interface in interfaces.values()} == {
            f"eth{idx}" for idx in range(nbr_interfaces)
        }
        counts[nbr_interfaces] = counting_db.count_for(RelationshipGetPeerQuery.name)

    assert counts[1] == counts[5] == 1
