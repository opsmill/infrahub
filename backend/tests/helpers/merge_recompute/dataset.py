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


def build_profile_schema(cross_relationship_hfid: bool = False) -> SchemaRoot:
    """Two kinds: a peer, and a main node carrying all three derived families.

    With ``cross_relationship_hfid`` the node's human-friendly id reads the peer across the
    relationship instead of only its own name, so a peer rename has to refresh the stored HFID.
    """
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
        human_friendly_id=["name__value", "peer__name__value"] if cross_relationship_hfid else ["name__value"],
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


TRANSFORM_NAMESPACE = "Testing"
TRANSFORM_OWNER_KIND = "TestingTShirt"
TRANSFORM_PEER_KIND = "TestingColor"
TRANSFORM_REPO_NAME = "computed-attributes-functional"


def build_transform_schema_dict() -> dict:
    """A Python-transform computed attribute that reads a peer across a relationship.

    The kind, attribute and transform names match the transform fixture repository, whose
    query reads the owner's name plus the peer's name and description. Editing a peer is
    therefore the cross-node change that drives the owner's recompute.

    Carries no display label and no human-friendly id, so the Python attribute is the only
    derived value on these kinds and the measured recompute is attributable to that family
    alone.
    """
    return {
        "version": "1.0",
        "nodes": [
            {
                "name": "Color",
                "namespace": TRANSFORM_NAMESPACE,
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "optional": False, "unique": True},
                    {"name": "description", "kind": "Text", "optional": False},
                ],
            },
            {
                "name": "TShirt",
                "namespace": TRANSFORM_NAMESPACE,
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "optional": False},
                    {
                        "name": "pitch",
                        "kind": "Text",
                        "optional": True,
                        "read_only": True,
                        "computed_attribute": {"kind": "TransformPython", "transform": "TShirtPitch"},
                    },
                ],
                "relationships": [
                    {
                        "name": "color",
                        "peer": TRANSFORM_PEER_KIND,
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


INTERFACE_NAMESPACE = "Testing"
DEVICE_KIND = "TestingDevice"
INTERFACE_KIND = "TestingInterface"


def build_interface_hfid_schema_dict() -> dict:
    """A device and an interface whose identity reads the device across the relationship.

    The interface's human-friendly id and display label both read the device name, so its stored
    identity depends on a peer attribute. Renaming the device must rewrite the stored id, the
    cross-relationship case that a self-only id never reaches.
    """
    return {
        "version": "1.0",
        "nodes": [
            {
                "name": "Device",
                "namespace": INTERFACE_NAMESPACE,
                "default_filter": "name__value",
                "display_label": "{{ name__value }}",
                "attributes": [{"name": "name", "kind": "Text", "optional": False, "unique": True}],
            },
            {
                "name": "Interface",
                "namespace": INTERFACE_NAMESPACE,
                "default_filter": "name__value",
                "display_label": "{{ device__name__value }} :: {{ name__value }}",
                "human_friendly_id": ["name__value", "device__name__value"],
                "uniqueness_constraints": [["device", "name__value"]],
                "attributes": [{"name": "name", "kind": "Text", "optional": False}],
                "relationships": [{"name": "device", "peer": DEVICE_KIND, "optional": False, "cardinality": "one"}],
            },
        ],
    }


LOCATION_NAMESPACE = "Testing"
METRO_KIND = "TestingMetro"
SITE_KIND = "TestingSite"
RACK_KIND = "TestingRack"


def build_location_cascade_schema_dict() -> dict:
    """A metro -> site -> rack chain that propagates a top-level rename two hops.

    The site's short name is a computed attribute reading the metro name across the relationship.
    The site display label reads the metro directly, so it refreshes on the first hop. The rack
    display label reads the site's short name across its own relationship, so it moves only after
    the site's short name is rewritten: the recompute has to chain from that write to the rack. A
    self-only display label never exercises this second hop.
    """
    return {
        "version": "1.0",
        "nodes": [
            {
                "name": "Metro",
                "namespace": LOCATION_NAMESPACE,
                "default_filter": "name__value",
                "display_label": "{{ name__value }}",
                "attributes": [{"name": "name", "kind": "Text", "optional": False, "unique": True}],
            },
            {
                "name": "Site",
                "namespace": LOCATION_NAMESPACE,
                "default_filter": "name__value",
                "display_label": "{{ metro__name__value }}-{{ name__value }}",
                "attributes": [
                    {"name": "name", "kind": "Text", "optional": False, "unique": True},
                    {
                        "name": "shortname",
                        "kind": "Text",
                        "optional": True,
                        "read_only": True,
                        "computed_attribute": {
                            "kind": "Jinja2",
                            "jinja2_template": "{{ metro__name__value }}-{{ name__value }}",
                        },
                    },
                ],
                "relationships": [{"name": "metro", "peer": METRO_KIND, "optional": False, "cardinality": "one"}],
            },
            {
                "name": "Rack",
                "namespace": LOCATION_NAMESPACE,
                "default_filter": "name__value",
                "display_label": "{{ site__shortname__value }} :: {{ name__value }}",
                "attributes": [{"name": "name", "kind": "Text", "optional": False, "unique": True}],
                "relationships": [{"name": "site", "peer": SITE_KIND, "optional": False, "cardinality": "one"}],
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

    The branch is created here (not passed in) so the baseline nodes exist on default before the
    fork, otherwise the branch cannot see them.

    ``mutate_target`` picks which diff the change lands in: ``"branch"`` mutates on the branch (the
    merge diff), ``"default"`` mutates on default after the fork (the rebase diff). ``mutate_kind``
    picks what changes: ``"main"`` edits a node's own name (recomputed inline on save, no async
    fan-out), ``"peer"`` edits a read peer (each reader recomputes across the relationship, the
    cross-node fan-out).
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
