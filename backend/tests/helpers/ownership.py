"""Data set and helpers for the tests that write and read the owners and sources of nodes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
import ujson

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_TARGET_HOLDER,
    HolderKey,
    HolderKind,
    ResolvedOwnership,
    StoredOwnerState,
    field_holder,
)
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.resolver import OwnershipResolver
from infrahub.core.ownership.writer import OwnershipWriter
from infrahub.core.timestamp import Timestamp
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

USER_ID = "test-user-id"
OWNERS_FIELD = "node_metadata__owners"
TARGET_OWNERS_FIELD = "node_metadata__target_owners"
SOURCES_FIELD = "node_metadata__sources"
GROUP_NAMES = ("dc-emea", "network-emea", "security")
SECONDS_TO_WAIT = 30.0
SECONDS_BETWEEN_POLLS = 0.05
BLOCKED_TRANSACTIONS = """
SHOW TRANSACTIONS YIELD database, status
WHERE database = $database AND status STARTS WITH "Blocked"
RETURN count(*) AS blocked
"""

# The owner edges of a repository are written as an earlier release stored them, because a repository is refused
# as owner from the upgrade.
ADD_ATTRIBUTE_OWNER = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(holder:Attribute {name: "color"})
MATCH (owner:Node {uuid: $owner_id})
CREATE (holder)-[:HAS_OWNER {branch: $branch, branch_level: $branch_level, status: "active", from: $at}]->(owner)
"""
ADD_NAME_OWNER = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(holder:Attribute {name: "name"})
MATCH (owner:Node {uuid: $owner_id})
CREATE (holder)-[:HAS_OWNER {branch: $branch, branch_level: $branch_level, status: "active", from: $at}]->(owner)
"""
ADD_LINK_OWNER = """
MATCH (:Node {uuid: $node_id})-[:IS_RELATED]-(holder:Relationship)
MATCH (owner:Node {uuid: $owner_id})
CREATE (holder)-[:HAS_OWNER {branch: $branch, branch_level: $branch_level, status: "active", from: $at}]->(owner)
"""


@dataclass
class OwnerDataset:
    """The tenant `tenant-a` holds the racks `rack-a` and `rack-b`, and `rack-a` holds the device `device-a`."""

    ids: dict[str, str]
    """The ID of each account group and each node, by name."""

    def owners(self, names: tuple[str, ...] | None) -> tuple[str, ...] | None:
        """Return the sorted IDs of account groups, with None for inherit and an empty tuple for "no owner"."""
        return None if names is None else tuple(sorted(self.ids[name] for name in names))

    def owner_list(self, names: tuple[str, ...] | None) -> str | None:
        """Return the value that the diff gives to these owners."""
        owner_ids = self.owners(names)
        return None if owner_ids is None else ujson.dumps(list(owner_ids))

    def owner_labels(self, names: tuple[str, ...], deleted: tuple[str, ...] = (), mark: str = "deleted owner") -> str:
        """Return the label that the diff gives to these owners, with the mark of each deleted owner."""
        by_id = sorted(names, key=lambda name: self.ids[name])
        return ", ".join(mark if name in deleted else name for name in by_id)


async def add_node(db: InfrahubDatabase, kind: str, **data: Any) -> Node:
    node = await Node.init(db=db, schema=kind)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


async def create_groups(db: InfrahubDatabase, names: tuple[str, ...] = GROUP_NAMES) -> dict[str, str]:
    """Create an account group for each name and return their IDs by name."""
    return {name: (await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=name)).id for name in names}


async def load_owner_dataset(db: InfrahubDatabase, default_branch: Branch) -> OwnerDataset:
    registry.schema.register_schema(schema=OWNERSHIP_SCHEMA, branch=default_branch.name)
    ids = await create_groups(db=db)
    ids["tenant-a"] = (await add_node(db=db, kind="TestTenant", name="tenant-a")).id
    for name in ("rack-a", "rack-b"):
        ids[name] = (await add_node(db=db, kind="TestRack", name=name, tenant=ids["tenant-a"])).id
    ids["device-a"] = (await add_node(db=db, kind="TestDevice", name="device-a", rack=ids["rack-a"])).id
    return OwnerDataset(ids=ids)


async def set_owners(
    db: InfrahubDatabase,
    branch: Branch,
    node_id: str,
    owner_ids: tuple[str, ...] | None,
    holder: HolderKey = NODE_HOLDER,
    at: Timestamp | None = None,
) -> None:
    """Write the owners of one holder of the node through the owner writer, which does not check the owner kinds."""
    node = await NodeManager.get_one(db=db, branch=branch, id=node_id, raise_on_error=True)
    writer = OwnershipWriter(repository=OwnershipRepository(db=db, branch=branch, at=None))
    await writer.apply(
        node=node, holder=holder, state=StoredOwnerState(owner_ids=owner_ids), at=at or Timestamp(), user_id=USER_ID
    )


async def read_owners(
    db: InfrahubDatabase, branch: Branch, node_id: str, holder: HolderKey = NODE_HOLDER
) -> tuple[str, ...] | None:
    """Return the owners that one holder of the node stores, as the branch reads them."""
    stored = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[node_id], attributes=True)
    return stored[node_id].get(holder).owner_ids


async def resolve_owners(db: InfrahubDatabase, branch: Branch, node_id: str) -> ResolvedOwnership:
    """Return the owners that apply to the node, own or inherited, as the branch reads them."""
    resolver = OwnershipResolver(repository=OwnershipRepository(db=db, branch=branch, at=None))
    return (await resolver.resolve(node_ids=[node_id]))[node_id]


async def site_template(db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset) -> Node:
    """Create a site template that gives one owner to its sites, to their names and to their children."""
    schema = registry.schema.get_node_schema(name="TestSite", branch=default_branch)
    template = await add_node(db=db, kind="TemplateTestSite", template_name="emea-site")
    for holder in (
        NODE_TARGET_HOLDER,
        field_holder(schema=schema, field_name="name", target=True),
        field_holder(schema=schema, field_name="children", target=True),
    ):
        assert holder is not None
        await set_owners(
            db=db, branch=default_branch, node_id=template.id, owner_ids=dataset.owners(("dc-emea",)), holder=holder
        )
    return template


async def site_from(db: InfrahubDatabase, branch: Branch, template: Node, name: str) -> str:
    site = await create_node(
        data={"name": name, "object_template": {"id": template.id}},
        db=db,
        branch=branch,
        schema=registry.schema.get_node_schema(name="TestSite", branch=branch),
    )
    return site.id


async def template_copies(
    db: InfrahubDatabase, branch: Branch, node_id: str
) -> dict[HolderKind, tuple[tuple[str, ...] | None, str | None]]:
    """Return the owners of each holder of the node and the template that they are a copy from, as the branch reads them."""
    stored = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[node_id], attributes=True)
    return {holder.kind: (state.owner_ids, state.template_id) for holder, state in stored[node_id].holders.items()}


def copies(owner_ids: tuple[str, ...] | None, template_id: str | None) -> dict[HolderKind, tuple[object, object]]:
    """Return the owners and the template of copy that a site reads for its node, its attribute and its field."""
    return dict.fromkeys((HolderKind.NODE, HolderKind.ATTRIBUTE, HolderKind.FIELD_SET), (owner_ids, template_id))


async def add_owner_edge(db: InfrahubDatabase, query: str, branch: Branch, node_id: str, owner_id: str) -> None:
    await db.execute_query(
        query=query,
        params={
            "node_id": node_id,
            "owner_id": owner_id,
            "branch": branch.name,
            "branch_level": branch.hierarchy_level,
            "at": Timestamp().to_string(),
        },
    )


async def create_car(db: InfrahubDatabase, name: str, person: Node, owner_id: str | None = None) -> Node:
    """Create a car of the person, with an owner on its color."""
    car = await Node.init(db=db, schema="TestCar")
    await car.new(db=db, name=name, owner=person, color={"value": "#000000", "owner": owner_id})
    await car.save(db=db)
    return car


async def wait_for_the_other_write(
    db: InfrahubDatabase, other: asyncio.Future[Any], event: asyncio.Event | None = None
) -> None:
    """Return once `event` is set, once a transaction waits for a lock, or once the other write ends without a wait."""
    params = {"database": config.SETTINGS.database.database_name}
    try:
        async with asyncio.timeout(SECONDS_TO_WAIT):
            while not other.done() and not (event and event.is_set()):
                if (await db.execute_query(query=BLOCKED_TRANSACTIONS, params=params))[0]["blocked"]:
                    return
                await asyncio.sleep(SECONDS_BETWEEN_POLLS)
    except TimeoutError:
        pytest.fail(f"The other write neither waited for a lock nor ended within {SECONDS_TO_WAIT} seconds")
