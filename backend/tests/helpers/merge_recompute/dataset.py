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


CHAIN_NAMESPACE = "Testing"


def chain_kind(level: int) -> str:
    """Schema kind for one level of the computed-attribute chain (level 1 is the root)."""
    return f"{CHAIN_NAMESPACE}ChainL{level}"


def chain_kinds(levels: int) -> list[str]:
    return [chain_kind(level) for level in range(1, levels + 1)]


def _chain_template(level: int) -> str:
    # Level 2 reads the root's plain name; deeper levels read the level below's computed
    # summary, so one root edit only reaches the tip by propagating hop by hop.
    return "{{ source__name__value }}" if level == 2 else "{{ source__summary__value }}"


def build_chain_schema(levels: int = 3) -> SchemaRoot:
    """A linear chain of computed attributes: level i reads level i-1 across ``source``.

    Level 1 carries a plain ``name``; every deeper level adds a ``summary`` computed from
    the level below it, so a single root edit has to cascade through every level to settle.

    Raises:
        ValueError: if ``levels`` is below two (a chain needs a root and one reader).

    """
    if levels < 2:
        raise ValueError("a computed-attribute chain needs at least two levels")
    nodes: list[NodeSchema] = []
    for level in range(1, levels + 1):
        attributes = [AttributeSchema(name="name", kind="Text", optional=False, unique=True)]
        relationships: list[RelationshipSchema] = []
        if level > 1:
            attributes.append(
                AttributeSchema(
                    name="summary",
                    kind="Text",
                    optional=True,
                    read_only=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.JINJA2,
                        jinja2_template=_chain_template(level),
                    ),
                )
            )
            relationships.append(
                RelationshipSchema(
                    name="source",
                    optional=False,
                    peer=chain_kind(level - 1),
                    cardinality=RelationshipCardinality.ONE,
                )
            )
        nodes.append(
            NodeSchema(
                name=f"ChainL{level}",
                namespace=CHAIN_NAMESPACE,
                label=f"Chain Level {level}",
                default_filter="name__value",
                display_label="{{ name__value }}",
                human_friendly_id=["name__value"],
                uniqueness_constraints=[["name__value"]],
                attributes=attributes,
                relationships=relationships,
            )
        )
    return SchemaRoot(nodes=nodes)


async def load_chain_schema(db: InfrahubDatabase, levels: int = 3, branch_name: str | None = None) -> None:
    await load_schema(db=db, schema=build_chain_schema(levels=levels), branch_name=branch_name, update_db=True)


def build_chain_schema_dict(levels: int = 3) -> dict:
    """The chain schema in the user-facing (SDK ``schema.load``) format for full-stack tests.

    Raises:
        ValueError: if ``levels`` is below two (a chain needs a root and one reader).

    """
    if levels < 2:
        raise ValueError("a computed-attribute chain needs at least two levels")
    nodes: list[dict] = []
    for level in range(1, levels + 1):
        attributes: list[dict] = [{"name": "name", "kind": "Text", "optional": False, "unique": True}]
        node: dict = {
            "name": f"ChainL{level}",
            "namespace": CHAIN_NAMESPACE,
            "default_filter": "name__value",
            "display_label": "{{ name__value }}",
            "human_friendly_id": ["name__value"],
            "attributes": attributes,
        }
        if level > 1:
            attributes.append(
                {
                    "name": "summary",
                    "kind": "Text",
                    "optional": True,
                    "read_only": True,
                    "computed_attribute": {"kind": "Jinja2", "jinja2_template": _chain_template(level)},
                }
            )
            node["relationships"] = [
                {"name": "source", "peer": chain_kind(level - 1), "optional": False, "cardinality": "one"}
            ]
        nodes.append(node)
    return {"version": "1.0", "nodes": nodes}


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

    # Namespace the seeded names by branch so repeated seed_branch calls in one test (e.g. across
    # scales) do not create duplicate names on the shared default branch, which the merge-time
    # uniqueness gate rejects.
    for index in range(changed_nodes):
        peer = await Node.init(db=db, schema=PROFILE_PEER_KIND, branch=default_branch)
        await peer.new(db=db, name=f"{branch_name}-peer-{index:05d}")
        await peer.save(db=db)
        peer_ids.append(peer.id)

        node = await Node.init(db=db, schema=PROFILE_NODE_KIND, branch=default_branch)
        await node.new(db=db, name=f"{branch_name}-node-{index:05d}", peer=peer)
        await node.save(db=db)
        main_ids.append(node.id)

    branch = await create_branch(branch_name=branch_name, db=db)

    mutation_branch = branch if mutate_target == "branch" else default_branch
    target_ids, prefix = (
        (main_ids, f"{branch_name}-node") if mutate_kind == "main" else (peer_ids, f"{branch_name}-peer")
    )
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
