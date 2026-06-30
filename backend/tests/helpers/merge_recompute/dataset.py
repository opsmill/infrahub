"""Synthetic dataset for the merge/rebase recompute profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import ComputedAttributeKind, RelationshipCardinality
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

PROFILE_NAMESPACE = "Testing"
PROFILE_NODE_KIND = "TestingProfileNode"
PROFILE_PEER_KIND = "TestingProfilePeer"


def build_profile_schema() -> SchemaRoot:
    """Two kinds: a peer, and a main node carrying all three derived families."""
    peer = NodeSchema(
        name="ProfilePeer",
        namespace=PROFILE_NAMESPACE,
        label="Profile Peer",
        default_filter="name__value",
        display_label="{{ name__value }}",
        uniqueness_constraints=[["name__value"]],
        attributes=[
            AttributeSchema(name="name", kind="Text", optional=False, unique=True),
        ],
    )
    node = NodeSchema(
        name="ProfileNode",
        namespace=PROFILE_NAMESPACE,
        label="Profile Node",
        default_filter="name__value",
        display_label="{{ name__value }} via {{ peer__name__value }}",
        human_friendly_id=["name__value"],
        uniqueness_constraints=[["name__value"]],
        attributes=[
            AttributeSchema(name="name", kind="Text", optional=False, unique=True),
            AttributeSchema(
                name="summary",
                kind="Text",
                optional=True,
                read_only=True,
                computed_attribute=ComputedAttribute(
                    kind=ComputedAttributeKind.JINJA2,
                    jinja2_template="{{ name__value }} on {{ peer__name__value }}",
                ),
            ),
        ],
        relationships=[
            RelationshipSchema(
                name="peer",
                optional=False,
                peer=PROFILE_PEER_KIND,
                cardinality=RelationshipCardinality.ONE,
            ),
        ],
    )
    return SchemaRoot(nodes=[peer, node])


async def load_profile_schema(db: InfrahubDatabase, branch_name: str | None = None) -> None:
    """Register the profile schema and persist it so real nodes can be created."""
    await load_schema(db=db, schema=build_profile_schema(), branch_name=branch_name, update_db=True)


def build_profile_schema_dict() -> dict:
    """The same profile schema in the user-facing (SDK ``schema.load``) format.

    Used by the full-stack timing layer, which talks to a running instance through
    the SDK rather than the in-process database.
    """
    return {
        "version": "1.0",
        "nodes": [
            {
                "name": "ProfilePeer",
                "namespace": PROFILE_NAMESPACE,
                "default_filter": "name__value",
                "display_label": "{{ name__value }}",
                "attributes": [{"name": "name", "kind": "Text", "optional": False, "unique": True}],
            },
            {
                "name": "ProfileNode",
                "namespace": PROFILE_NAMESPACE,
                "default_filter": "name__value",
                "display_label": "{{ name__value }} via {{ peer__name__value }}",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "optional": False, "unique": True},
                    {
                        "name": "summary",
                        "kind": "Text",
                        "optional": True,
                        "read_only": True,
                        "computed_attribute": {
                            "kind": "Jinja2",
                            "jinja2_template": "{{ name__value }} on {{ peer__name__value }}",
                        },
                    },
                ],
                "relationships": [
                    {
                        "name": "peer",
                        "peer": PROFILE_PEER_KIND,
                        "optional": False,
                        "cardinality": "one",
                    }
                ],
            },
        ],
    }


@dataclass(frozen=True)
class SeededDataset:
    branch: Branch
    branch_name: str
    main_ids: list[str]
    peer_ids: list[str]
    changed_node_ids: list[str]
    changed_nodes: int


async def seed_branch(
    *,
    db: InfrahubDatabase,
    default_branch: Branch,
    branch_name: str,
    changed_nodes: int,
    mutate_target: str = "branch",
    mutate_kind: str = "main",
) -> SeededDataset:
    """Create the baseline on default, fork ``branch_name``, mutate ``changed_nodes`` nodes.

    The branch is created here (not passed in) because the baseline nodes must
    exist on the default branch before the fork point, or they are invisible to
    the branch.

    ``mutate_target`` selects the operation under profile:
    - ``"branch"`` mutates on the branch, so the change enters the *merge* diff
      (branch into default).
    - ``"default"`` mutates on default *after* the fork, so the change enters the
      *rebase* diff (default's intervening changes replayed into the branch).

    ``mutate_kind`` selects what changes:
    - ``"main"`` edits the mains' own ``name``. Their derived values recompute
      inline on save, so this produces node events but no asynchronous fan-out.
    - ``"peer"`` edits the peers' ``name``. The mains read the peer, so each main
      recomputes asynchronously: this is the cross-node fan-out the merge path pays.
    """
    peer_ids: list[str] = []
    main_ids: list[str] = []

    for index in range(changed_nodes):
        peer = await Node.init(db=db, schema=PROFILE_PEER_KIND, branch=default_branch)
        await peer.new(db=db, name=f"profile-peer-{index:05d}")
        await peer.save(db=db)
        peer_ids.append(peer.id)

        node = await Node.init(db=db, schema=PROFILE_NODE_KIND, branch=default_branch)
        await node.new(db=db, name=f"profile-node-{index:05d}", peer=peer)
        await node.save(db=db)
        main_ids.append(node.id)

    branch = await create_branch(branch_name=branch_name, db=db)

    mutation_branch = branch if mutate_target == "branch" else default_branch
    target_ids, prefix = (main_ids, "profile-node") if mutate_kind == "main" else (peer_ids, "profile-peer")
    changed_node_ids: list[str] = []
    for index, node_id in enumerate(target_ids):
        node_to_mutate = await NodeManager.get_one(id=node_id, branch=mutation_branch, db=db)
        node_to_mutate.get_attribute(name="name").value = f"{prefix}-{index:05d}-edited"
        await node_to_mutate.save(db=db)
        changed_node_ids.append(node_id)

    return SeededDataset(
        branch=branch,
        branch_name=branch_name,
        main_ids=main_ids,
        peer_ids=peer_ids,
        changed_node_ids=changed_node_ids,
        changed_nodes=changed_nodes,
    )
