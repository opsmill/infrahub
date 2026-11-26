from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.ownership.input import OwnerInputParser
from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_SOURCES_HOLDER,
    NODE_TARGET_HOLDER,
    HolderKey,
    StoredOwnerState,
)
from infrahub.core.schema import AttributeSchema, GenericSchema, MainSchemaTypes, NodeSchema, SchemaRoot, TemplateSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.exceptions import ValidationError

GROUP_ID = "group-emea-id"
ACCOUNT_ID = "account-admin-id"
OPS_GROUP_ID = "group-ops-id"
OPS_ACCOUNT_ID = "account-ops-id"
PROFILE_ID = "profile-base-id"
TAG_ID = "tag-blue-id"

NAME_ATTRIBUTE = AttributeSchema(name="name", kind="Text", unique=True)
SCHEMA = SchemaRoot(
    generics=[
        GenericSchema(
            name="GenericAccount", namespace="Core", human_friendly_id=["name__value"], attributes=[NAME_ATTRIBUTE]
        )
    ],
    nodes=[
        NodeSchema(name="Account", namespace="Core", inherit_from=["CoreGenericAccount"]),
        NodeSchema(
            name="AccountGroup", namespace="Core", human_friendly_id=["name__value"], attributes=[NAME_ATTRIBUTE]
        ),
        NodeSchema(name="Tag", namespace="Builtin", human_friendly_id=["name__value"], attributes=[NAME_ATTRIBUTE]),
        NodeSchema(name="Device", namespace="Test", attributes=[NAME_ATTRIBUTE]),
    ],
)


OBJECT_TEMPLATE = TemplateSchema(name="TestDevice", namespace="Template")


def _schema(parser: OwnerInputParser, kind: str) -> MainSchemaTypes:
    if kind == OBJECT_TEMPLATE.kind:
        return OBJECT_TEMPLATE
    return parser.schema_branch.get(name=kind, duplicate=False)


class InMemoryOwnerLookup:
    def __init__(self) -> None:
        self.labels: dict[str, set[str]] = {
            GROUP_ID: {"Node", "CoreAccountGroup"},
            ACCOUNT_ID: {"Node", "CoreAccount", "CoreGenericAccount"},
            TAG_ID: {"Node", "BuiltinTag"},
        }
        self.ids_by_hfid: dict[tuple[str, tuple[str, ...]], list[str]] = {
            ("CoreAccountGroup", ("emea",)): [GROUP_ID],
            ("CoreAccount", ("admin",)): [ACCOUNT_ID],
            ("CoreGenericAccount", ("admin",)): [ACCOUNT_ID],
            ("CoreAccountGroup", ("ops",)): [OPS_GROUP_ID],
            ("CoreAccount", ("ops",)): [OPS_ACCOUNT_ID],
            ("CoreGenericAccount", ("ops",)): [OPS_ACCOUNT_ID],
            ("ProfileTestDevice", ("base",)): [PROFILE_ID],
        }

    async def read_labels(self, node_ids: list[str]) -> dict[str, set[str]]:
        return {node_id: self.labels[node_id] for node_id in node_ids if node_id in self.labels}

    async def find_ids_by_hfids(self, kind: str, hfids: list[tuple[str, ...]]) -> dict[tuple[str, ...], list[str]]:
        return {hfid: self.ids_by_hfid[kind, hfid] for hfid in hfids if (kind, hfid) in self.ids_by_hfid}


@pytest.fixture(scope="module")
def parser() -> OwnerInputParser:
    schema_branch = SchemaBranch(cache={}, name="main")
    schema_branch.load_schema(schema=SCHEMA)
    schema_branch.process()
    return OwnerInputParser(schema_branch=schema_branch, lookup=InMemoryOwnerLookup())


@dataclass
class AcceptedInputTestCase:
    name: str
    node_metadata: dict[str, Any]
    expected: dict[HolderKey, StoredOwnerState]
    kind: str = "BuiltinTag"
    """The kind of the node that gets the input."""

    data: dict[str, Any] | None = None
    """The input of the mutation, with the fields of the node."""


ACCEPTED_INPUT_TEST_CASES: list[AcceptedInputTestCase] = [
    AcceptedInputTestCase(name="key_left_out_gives_no_state", node_metadata={}, expected={}),
    AcceptedInputTestCase(
        name="null_gives_inherit",
        node_metadata={"owners": None},
        expected={NODE_HOLDER: StoredOwnerState(owner_ids=None)},
    ),
    AcceptedInputTestCase(
        name="empty_list_gives_no_owner",
        node_metadata={"owners": []},
        expected={NODE_HOLDER: StoredOwnerState(owner_ids=())},
    ),
    AcceptedInputTestCase(
        name="list_gives_each_owner_one_time",
        node_metadata={
            "owners": [{"id": GROUP_ID}, {"kind": "CoreAccount", "hfid": ["admin"]}, {"id": GROUP_ID}],
        },
        expected={NODE_HOLDER: StoredOwnerState(owner_ids=(GROUP_ID, ACCOUNT_ID))},
    ),
    AcceptedInputTestCase(
        name="name_with_a_kind_is_a_node_of_the_kind",
        node_metadata={
            "owners": [
                {"kind": "CoreAccount", "name": "admin"},
                {"kind": "CoreAccountGroup", "name": "ops"},
                {"kind": "CoreAccount", "name": "ops"},
            ]
        },
        expected={NODE_HOLDER: StoredOwnerState(owner_ids=(ACCOUNT_ID, OPS_GROUP_ID, OPS_ACCOUNT_ID))},
    ),
    AcceptedInputTestCase(
        name="account_id_is_accepted",
        node_metadata={"owners": [{"id": ACCOUNT_ID}]},
        expected={NODE_HOLDER: StoredOwnerState(owner_ids=(ACCOUNT_ID,))},
    ),
    AcceptedInputTestCase(
        name="profile_gives_owners_and_has_own_owners",
        kind="ProfileTestDevice",
        node_metadata={"owners": [{"id": ACCOUNT_ID}], "target_owners": [{"id": GROUP_ID}]},
        expected={
            NODE_HOLDER: StoredOwnerState(owner_ids=(ACCOUNT_ID,)),
            NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=(GROUP_ID,)),
        },
    ),
    AcceptedInputTestCase(
        name="profile_gives_no_owner",
        kind="ProfileTestDevice",
        node_metadata={"target_owners": []},
        expected={NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=())},
    ),
    AcceptedInputTestCase(
        name="profile_gives_nothing",
        kind="ProfileTestDevice",
        node_metadata={"target_owners": None},
        expected={NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=None)},
    ),
    AcceptedInputTestCase(
        name="object_template_gives_owners_by_hfid",
        kind="TemplateTestDevice",
        node_metadata={"target_owners": [{"kind": "CoreAccountGroup", "hfid": ["emea"]}]},
        expected={NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=(GROUP_ID,))},
    ),
    AcceptedInputTestCase(
        name="list_gives_each_source_one_time_next_to_the_owners",
        node_metadata={
            "owners": [{"id": GROUP_ID}],
            "sources": [{"id": GROUP_ID}, {"kind": "CoreAccount", "hfid": ["admin"]}, {"id": GROUP_ID}],
        },
        expected={
            NODE_HOLDER: StoredOwnerState(owner_ids=(GROUP_ID,)),
            NODE_SOURCES_HOLDER: StoredOwnerState(owner_ids=(GROUP_ID, ACCOUNT_ID)),
        },
    ),
    AcceptedInputTestCase(
        name="profile_is_a_source_by_kind_with_hfid_and_by_kind_with_name",
        node_metadata={
            "sources": [{"kind": "ProfileTestDevice", "hfid": ["base"]}, {"kind": "ProfileTestDevice", "name": "base"}]
        },
        expected={NODE_SOURCES_HOLDER: StoredOwnerState(owner_ids=(PROFILE_ID,))},
    ),
    AcceptedInputTestCase(
        name="null_gives_no_source",
        node_metadata={"sources": None},
        expected={NODE_SOURCES_HOLDER: StoredOwnerState(owner_ids=None)},
    ),
    AcceptedInputTestCase(
        name="empty_list_gives_no_source",
        node_metadata={"sources": []},
        expected={NODE_SOURCES_HOLDER: StoredOwnerState(owner_ids=None)},
    ),
    AcceptedInputTestCase(
        name="field_owners_entry_without_owners_gives_no_state",
        node_metadata={"field_owners": [{"field": "name"}]},
        expected={},
    ),
    AcceptedInputTestCase(
        name="target_field_owners_entry_without_owners_gives_no_state",
        kind="TemplateTestDevice",
        node_metadata={"target_field_owners": [{"field": "name"}]},
        expected={},
    ),
    AcceptedInputTestCase(
        name="owner_of_an_attribute_gives_no_state",
        node_metadata={},
        data={"name": {"owner": GROUP_ID}},
        expected={},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in ACCEPTED_INPUT_TEST_CASES])
async def test_parse_accepted_input(parser: OwnerInputParser, test_case: AcceptedInputTestCase) -> None:
    schema = _schema(parser=parser, kind=test_case.kind)

    states = await parser.parse(node_metadata=test_case.node_metadata, schema=schema, data=test_case.data)

    assert states == test_case.expected


@dataclass
class RefusedInputTestCase:
    name: str
    owners: Any
    expected_message: str
    key: str = "owners"
    kind: str = "BuiltinTag"
    """The kind of the node that gets the input."""


REFUSED_INPUT_TEST_CASES: list[RefusedInputTestCase] = [
    RefusedInputTestCase(
        name="id_not_found_after_a_valid_owner",
        owners=[{"id": GROUP_ID}, {"id": "unknown-id"}],
        expected_message="Owner not found: unknown-id at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="hfid_not_found",
        owners=[{"kind": "CoreAccountGroup", "hfid": ["apac"]}],
        expected_message="Owner not found: CoreAccountGroup ['apac'] at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="id_of_another_kind",
        owners=[{"id": TAG_ID}],
        expected_message=f"Only an account or an account group can be an owner, not: {TAG_ID} at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="hfid_of_another_kind",
        owners=[{"kind": "BuiltinTag", "hfid": ["blue"]}],
        expected_message="Only an account or an account group can be an owner, not: BuiltinTag at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="unknown_kind",
        owners=[{"kind": "CoreUnknown", "hfid": ["emea"]}],
        expected_message="Unknown kind for an owner: CoreUnknown at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="name_of_an_account_group_without_kind",
        owners=[{"name": "emea"}],
        expected_message="Give the kind with the name of an owner: emea at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="name_of_an_account_and_of_an_account_group_without_kind",
        owners=[{"name": "ops"}],
        expected_message="Give the kind with the name of an owner: ops at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="name_with_another_kind",
        owners=[{"kind": "BuiltinTag", "name": "blue"}],
        expected_message="Only an account or an account group can be an owner, not: BuiltinTag at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="source_name_without_kind",
        key="sources",
        owners=[{"name": "emea"}],
        expected_message="Give the kind with the name of a source: emea at node_metadata.sources",
    ),
    RefusedInputTestCase(
        name="neither_id_nor_kind_with_hfid",
        owners=[{}],
        expected_message="Each owner must have an id, a kind and an hfid, or a kind and a name at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="kind_without_hfid",
        owners=[{"kind": "CoreAccountGroup"}],
        expected_message="Each owner must have an id, a kind and an hfid, or a kind and a name at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="hfid_without_kind",
        owners=[{"hfid": ["emea"]}],
        expected_message="Each owner must have an id, a kind and an hfid, or a kind and a name at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="hfid_of_the_wrong_length",
        owners=[{"kind": "CoreAccountGroup", "hfid": ["emea", "network"]}],
        expected_message="The hfid of CoreAccountGroup must have 1 value(s), not 2 at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="owners_that_are_not_a_list",
        owners=GROUP_ID,
        expected_message="Owners must be a list at node_metadata.owners",
    ),
    RefusedInputTestCase(
        name="owners_given_by_a_kind_that_is_not_a_profile_or_an_object_template",
        key="target_owners",
        owners=[{"id": GROUP_ID}],
        expected_message=(
            "Only a profile or an object template gives owners to its nodes, "
            "not: BuiltinTag at node_metadata.target_owners"
        ),
    ),
    RefusedInputTestCase(
        name="nothing_given_by_a_kind_that_is_not_a_profile_or_an_object_template",
        key="target_owners",
        owners=None,
        expected_message=(
            "Only a profile or an object template gives owners to its nodes, "
            "not: BuiltinTag at node_metadata.target_owners"
        ),
    ),
    RefusedInputTestCase(
        name="source_id_of_another_kind",
        key="sources",
        owners=[{"id": GROUP_ID}, {"id": TAG_ID}],
        expected_message=(
            "Only an account, an account group, a repository, a resource pool, a profile or an object template "
            f"can be a source, not: {TAG_ID} at node_metadata.sources"
        ),
    ),
    RefusedInputTestCase(
        name="source_hfid_of_another_kind",
        key="sources",
        owners=[{"kind": "BuiltinTag", "hfid": ["blue"]}],
        expected_message=(
            "Only an account, an account group, a repository, a resource pool, a profile or an object template "
            "can be a source, not: BuiltinTag at node_metadata.sources"
        ),
    ),
    RefusedInputTestCase(
        name="source_id_not_found",
        key="sources",
        owners=[{"id": "unknown-id"}],
        expected_message="Source not found: unknown-id at node_metadata.sources",
    ),
    RefusedInputTestCase(
        name="source_of_an_unknown_kind",
        key="sources",
        owners=[{"kind": "CoreUnknown", "hfid": ["emea"]}],
        expected_message="Unknown kind for a source: CoreUnknown at node_metadata.sources",
    ),
    RefusedInputTestCase(
        name="source_without_id_and_without_kind_with_hfid",
        key="sources",
        owners=[{}],
        expected_message=(
            "Each source must have an id, a kind and an hfid, or a kind and a name at node_metadata.sources"
        ),
    ),
    RefusedInputTestCase(
        name="sources_that_are_not_a_list",
        key="sources",
        owners=GROUP_ID,
        expected_message="Sources must be a list at node_metadata.sources",
    ),
    RefusedInputTestCase(
        name="field_owners_entry_without_owners_for_an_unknown_field",
        key="field_owners",
        owners=[{"field": "unknown"}],
        expected_message="unknown is not an attribute or a relationship of BuiltinTag at node_metadata.field_owners",
    ),
    RefusedInputTestCase(
        name="profile_gives_an_owner_of_another_kind",
        key="target_owners",
        kind="ProfileTestDevice",
        owners=[{"id": TAG_ID}],
        expected_message=(
            f"Only an account or an account group can be an owner, not: {TAG_ID} at node_metadata.target_owners"
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REFUSED_INPUT_TEST_CASES])
async def test_parse_refuses_the_whole_input(parser: OwnerInputParser, test_case: RefusedInputTestCase) -> None:
    schema = _schema(parser=parser, kind=test_case.kind)

    with pytest.raises(ValidationError) as exc:
        await parser.parse(node_metadata={test_case.key: test_case.owners}, schema=schema)

    assert exc.value.message == test_case.expected_message
