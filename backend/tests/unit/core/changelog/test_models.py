from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.changelog.models import AttributeChangelog, peer_relationships
from infrahub.core.constants import DiffAction, RelationshipCardinality, RelationshipDirection
from infrahub.core.constants.schema import PARENT_CHILD_IDENTIFIER
from infrahub.core.schema import NodeSchema, RelationshipSchema


@dataclass
class SensitiveAttributeTestCase:
    name: str
    kind: str
    value: Any
    value_previous: Any
    expected_status: DiffAction
    expected_has_updates: bool


SENSITIVE_ATTRIBUTE_TEST_CASES: list[SensitiveAttributeTestCase] = [
    SensitiveAttributeTestCase(
        name="hashed_password_changed",
        kind="HashedPassword",
        value="new_secret",
        value_previous="old_secret",
        expected_status=DiffAction.UPDATED,
        expected_has_updates=True,
    ),
    SensitiveAttributeTestCase(
        name="hashed_password_unchanged",
        kind="HashedPassword",
        value="same_secret",
        value_previous="same_secret",
        expected_status=DiffAction.UNCHANGED,
        expected_has_updates=False,
    ),
    SensitiveAttributeTestCase(
        name="hashed_password_added",
        kind="HashedPassword",
        value="new_secret",
        value_previous=None,
        expected_status=DiffAction.ADDED,
        expected_has_updates=True,
    ),
    SensitiveAttributeTestCase(
        name="hashed_password_removed",
        kind="HashedPassword",
        value=None,
        value_previous="old_secret",
        expected_status=DiffAction.REMOVED,
        expected_has_updates=True,
    ),
    SensitiveAttributeTestCase(
        name="password_changed",
        kind="Password",
        value="new_secret",
        value_previous="old_secret",
        expected_status=DiffAction.UPDATED,
        expected_has_updates=True,
    ),
    SensitiveAttributeTestCase(
        name="password_unchanged",
        kind="Password",
        value="same_secret",
        value_previous="same_secret",
        expected_status=DiffAction.UNCHANGED,
        expected_has_updates=False,
    ),
    SensitiveAttributeTestCase(
        name="password_added",
        kind="Password",
        value="new_secret",
        value_previous=None,
        expected_status=DiffAction.ADDED,
        expected_has_updates=True,
    ),
    SensitiveAttributeTestCase(
        name="password_removed",
        kind="Password",
        value=None,
        value_previous="old_secret",
        expected_status=DiffAction.REMOVED,
        expected_has_updates=True,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in SENSITIVE_ATTRIBUTE_TEST_CASES],
)
def test_sensitive_attribute_update_status(test_case: SensitiveAttributeTestCase) -> None:
    attr = AttributeChangelog(
        name="password",
        value=test_case.value,
        value_previous=test_case.value_previous,
        kind=test_case.kind,
    )

    assert attr.value_update_status == test_case.expected_status
    assert attr.has_updates == test_case.expected_has_updates


HIERARCHY_PEER_SCHEMA = NodeSchema(
    name="Site",
    namespace="Loc",
    relationships=[
        RelationshipSchema(
            name="parent",
            peer="LocRegion",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
        RelationshipSchema(
            name="children",
            peer="LocRack",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.MANY,
            direction=RelationshipDirection.INBOUND,
        ),
    ],
)

# A hierarchical node whose own children relationship uses a different identifier, so it holds
# only one side under `parent__child`.
ONE_SIDED_PEER_SCHEMA = NodeSchema(
    name="Room",
    namespace="Loc",
    relationships=[
        RelationshipSchema(
            name="parent",
            peer="LocSite",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
    ],
)


@dataclass
class PeerRelationshipCase:
    name: str
    peer: NodeSchema
    local: RelationshipSchema
    expected_names: list[str]


PEER_RELATIONSHIP_CASES: list[PeerRelationshipCase] = [
    PeerRelationshipCase(
        name="the_child_side_resolves_to_children",
        peer=HIERARCHY_PEER_SCHEMA,
        local=RelationshipSchema(
            name="parent",
            peer="LocSite",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
        expected_names=["children"],
    ),
    PeerRelationshipCase(
        name="the_parent_side_resolves_to_parent",
        peer=HIERARCHY_PEER_SCHEMA,
        local=RelationshipSchema(
            name="children",
            peer="LocSite",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.MANY,
            direction=RelationshipDirection.INBOUND,
        ),
        expected_names=["parent"],
    ),
    PeerRelationshipCase(
        # Schema validation only checks the peers the pair declares, so it never sees a third kind.
        name="a_third_kind_reusing_the_identifier_gets_every_candidate",
        peer=HIERARCHY_PEER_SCHEMA,
        local=RelationshipSchema(
            name="site",
            peer="LocSite",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.BIDIR,
        ),
        expected_names=["parent", "children"],
    ),
    PeerRelationshipCase(
        # Nothing mirrors an outbound side on a peer that only declares one. Report it anyway,
        # so a change that did happen is never dropped.
        name="a_lone_candidate_is_reported_even_when_it_does_not_mirror",
        peer=ONE_SIDED_PEER_SCHEMA,
        local=RelationshipSchema(
            name="parent",
            peer="LocRoom",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
        expected_names=["parent"],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PEER_RELATIONSHIP_CASES])
def test_peer_relationships(test_case: PeerRelationshipCase) -> None:
    """A hierarchy resolves by direction. When nothing mirrors it, every candidate is reported."""
    resolved = peer_relationships(peer_schema=test_case.peer, rel_schema=test_case.local)

    assert [relationship.name for relationship in resolved] == test_case.expected_names
