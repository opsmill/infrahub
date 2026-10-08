from __future__ import annotations

import copy
from dataclasses import dataclass

import pytest

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.exceptions import ValidationError
from infrahub.pools.scope import DivisionResolver, ScopeEntry, ScopeValidator
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_DEVICE_ATTRIBUTE,
    SCOPED_DEVICE_KIND,
    SCOPED_POOL_SCHEMA,
    SCOPED_SITE,
    SCOPED_SITE_KIND,
    SCOPED_TAG,
)

EQUIPMENT_KIND = "ScopeEquipment"
SWITCH_KIND = "ScopeSwitch"
ROUTER_KIND = "ScopeRouter"
UNIQUE_ATTRIBUTE = "asset_number"


def _schema_branch(name: str, schema: SchemaRoot) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name=name)
    schema_branch.load_schema(schema=copy.deepcopy(schema))
    schema_branch.process()
    return schema_branch


@pytest.fixture
def main_schema() -> SchemaBranch:
    return _schema_branch(name="main", schema=SCOPED_POOL_SCHEMA)


@pytest.fixture
def branch_schema_without_role() -> SchemaBranch:
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes = [attribute for attribute in device.attributes if attribute.name != "role"]
    return _schema_branch(name="b1", schema=SchemaRoot(nodes=[SCOPED_SITE, SCOPED_TAG, device]))


def test_an_entry_the_branch_schema_does_not_define_on_the_kind_is_dropped(main_schema: SchemaBranch) -> None:
    entries = DivisionResolver.entries_in_force(
        scope=["site", "rack", "role"], schema_branch=main_schema, kind=SCOPED_DEVICE_KIND
    )

    assert [entry.path for entry in entries] == ["site", "role"]


def test_an_entry_is_dropped_only_on_the_branch_whose_schema_lacks_it(
    main_schema: SchemaBranch, branch_schema_without_role: SchemaBranch
) -> None:
    scope = ["site", "role"]

    on_main = DivisionResolver.entries_in_force(scope=scope, schema_branch=main_schema, kind=SCOPED_DEVICE_KIND)
    on_branch = DivisionResolver.entries_in_force(
        scope=scope, schema_branch=branch_schema_without_role, kind=SCOPED_DEVICE_KIND
    )

    assert [entry.path for entry in on_main] == ["site", "role"]
    assert [entry.path for entry in on_branch] == ["site"]


def test_a_scope_of_only_unknown_entries_leaves_no_entry_in_force(main_schema: SchemaBranch) -> None:
    entries = DivisionResolver.entries_in_force(
        scope=["rack", "pod"], schema_branch=main_schema, kind=SCOPED_DEVICE_KIND
    )

    assert entries == ()


def test_a_kind_the_branch_schema_does_not_define_leaves_no_entry_in_force(main_schema: SchemaBranch) -> None:
    entries = DivisionResolver.entries_in_force(scope=["site", "role"], schema_branch=main_schema, kind="ScopeGone")

    assert entries == ()


@pytest.mark.parametrize("scope", [["site", "role"], ["role", "site"]])
def test_entries_keep_the_scope_order(main_schema: SchemaBranch, scope: list[str]) -> None:
    entries = DivisionResolver.entries_in_force(scope=scope, schema_branch=main_schema, kind=SCOPED_DEVICE_KIND)

    assert [entry.path for entry in entries] == scope


def test_a_relationship_entry_carries_the_relationship_identifier(main_schema: SchemaBranch) -> None:
    entries = DivisionResolver.entries_in_force(
        scope=["site", "role"], schema_branch=main_schema, kind=SCOPED_DEVICE_KIND
    )

    assert entries == (
        ScopeEntry(path="site", relationship_identifier="scope_device__site"),
        ScopeEntry(path="role"),
    )
    site, role = entries
    assert site.is_relationship
    assert not role.is_relationship


def _validator_schema() -> SchemaRoot:
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes.extend(
        [
            AttributeSchema(name="labels", kind="List", optional=False),
            AttributeSchema(name="settings", kind="JSON", optional=False),
            AttributeSchema(name=UNIQUE_ATTRIBUTE, kind="Number", optional=True, unique=True),
        ]
    )
    equipment = GenericSchema(
        name="Equipment",
        namespace="Scope",
        attributes=[AttributeSchema(name=SCOPED_DEVICE_ATTRIBUTE, kind="Number", optional=True)],
        relationships=[
            RelationshipSchema(
                name="site",
                peer=SCOPED_SITE_KIND,
                identifier="scope_equipment__site",
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            )
        ],
    )
    switch = NodeSchema(
        name="Switch",
        namespace="Scope",
        inherit_from=[EQUIPMENT_KIND],
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )
    router = NodeSchema(
        name="Router",
        namespace="Scope",
        inherit_from=[EQUIPMENT_KIND],
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="pod", kind="Text", optional=False),
        ],
    )
    return SchemaRoot(generics=[equipment], nodes=[SCOPED_SITE, SCOPED_TAG, device, switch, router])


@pytest.fixture
def scope_validator() -> ScopeValidator:
    return ScopeValidator(schema_branch=_schema_branch(name="main", schema=_validator_schema()))


@dataclass
class ScopeRefusalTestCase:
    name: str
    scope: list[str]
    expected_messages: list[str]
    """Substrings the refusal carries, the first naming the entry."""


SCOPE_REFUSAL_TEST_CASES: list[ScopeRefusalTestCase] = [
    ScopeRefusalTestCase(
        name="optional_attribute",
        scope=["description"],
        expected_messages=["'description'", f"must be required on {SCOPED_DEVICE_KIND}"],
    ),
    ScopeRefusalTestCase(
        name="optional_relationship",
        scope=["parent"],
        expected_messages=["'parent'", f"must be required on {SCOPED_DEVICE_KIND}"],
    ),
    ScopeRefusalTestCase(
        name="many_relationship",
        scope=["tags"],
        expected_messages=["'tags'", "must be of cardinality one"],
    ),
    ScopeRefusalTestCase(
        name="related_node_path",
        scope=["site__name__value"],
        expected_messages=["'site__name__value'", "cannot use attributes of related node, only the relationship"],
    ),
    ScopeRefusalTestCase(
        name="related_node_attribute_without_property",
        scope=["site__name"],
        expected_messages=["'site__name'", "cannot use attributes of related node, only the relationship"],
    ),
    ScopeRefusalTestCase(
        name="related_node_path_on_optional_relationship",
        scope=["parent__name__value"],
        expected_messages=["'parent__name__value'", "cannot use attributes of related node, only the relationship"],
    ),
    ScopeRefusalTestCase(
        name="attribute_value_with_extra_segment",
        scope=["role__value__junk"],
        expected_messages=["'role__value__junk'", "must name the attribute or its value"],
    ),
    ScopeRefusalTestCase(
        name="list_kind",
        scope=["labels"],
        expected_messages=["'labels'", "must be a single scalar value"],
    ),
    ScopeRefusalTestCase(
        name="json_kind",
        scope=["settings"],
        expected_messages=["'settings'", "must be a single scalar value"],
    ),
    ScopeRefusalTestCase(
        name="pool_own_attribute",
        scope=[SCOPED_DEVICE_ATTRIBUTE],
        expected_messages=[f"'{SCOPED_DEVICE_ATTRIBUTE}'", "cannot scope a pool by the attribute it allocates"],
    ),
    ScopeRefusalTestCase(
        name="duplicate_entry",
        scope=["site", "site"],
        expected_messages=["'site'", "is a duplicate"],
    ),
    ScopeRefusalTestCase(
        name="duplicate_after_normalisation",
        scope=["role", "role__value"],
        expected_messages=["'role__value'", "is a duplicate"],
    ),
    ScopeRefusalTestCase(
        name="entry_not_defined_on_the_kind",
        scope=["site", "rack"],
        expected_messages=["'rack'", f"is not defined on {SCOPED_DEVICE_KIND}"],
    ),
    ScopeRefusalTestCase(
        name="attribute_property_other_than_value",
        scope=["role__label"],
        expected_messages=["'role__label'", "must name the attribute or its value"],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in SCOPE_REFUSAL_TEST_CASES])
def test_a_scope_entry_that_cannot_divide_the_pool_is_refused_naming_the_entry(
    scope_validator: ScopeValidator, test_case: ScopeRefusalTestCase
) -> None:
    with pytest.raises(ValidationError) as exc:
        scope_validator.validate(kind=SCOPED_DEVICE_KIND, attribute_name=SCOPED_DEVICE_ATTRIBUTE, scope=test_case.scope)

    assert exc.value.message.endswith("at allocation_scope")
    for expected_message in test_case.expected_messages:
        assert expected_message in exc.value.message


@pytest.mark.parametrize("scope", [["site"], ["role"]])
def test_any_scope_on_a_pool_whose_attribute_is_unique_is_refused_naming_the_attribute(
    scope_validator: ScopeValidator, scope: list[str]
) -> None:
    with pytest.raises(ValidationError) as exc:
        scope_validator.validate(kind=SCOPED_DEVICE_KIND, attribute_name=UNIQUE_ATTRIBUTE, scope=scope)

    assert f"'{UNIQUE_ATTRIBUTE}'" in exc.value.message
    assert "is unique" in exc.value.message


def test_an_entry_the_kind_declares_but_the_generic_does_not_is_refused_naming_the_generic(
    scope_validator: ScopeValidator,
) -> None:
    with pytest.raises(ValidationError) as exc:
        scope_validator.validate(kind=ROUTER_KIND, attribute_name=SCOPED_DEVICE_ATTRIBUTE, scope=["site", "pod"])

    assert "'pod'" in exc.value.message
    assert EQUIPMENT_KIND in exc.value.message


@pytest.mark.parametrize("kind", [ROUTER_KIND, SWITCH_KIND, EQUIPMENT_KIND])
def test_an_entry_the_generic_declares_is_accepted(scope_validator: ScopeValidator, kind: str) -> None:
    assert scope_validator.validate(kind=kind, attribute_name=SCOPED_DEVICE_ATTRIBUTE, scope=["site"]) == ("site",)


def test_an_entry_on_a_generic_pool_that_only_an_implementing_kind_declares_is_refused(
    scope_validator: ScopeValidator,
) -> None:
    with pytest.raises(ValidationError) as exc:
        scope_validator.validate(kind=EQUIPMENT_KIND, attribute_name=SCOPED_DEVICE_ATTRIBUTE, scope=["pod"])

    assert "'pod'" in exc.value.message
    assert f"is not defined on {EQUIPMENT_KIND}" in exc.value.message


def test_an_attribute_entry_with_the_value_property_is_normalised_to_the_attribute_name(
    scope_validator: ScopeValidator,
) -> None:
    normalised = scope_validator.validate(
        kind=SCOPED_DEVICE_KIND, attribute_name=SCOPED_DEVICE_ATTRIBUTE, scope=["role__value"]
    )

    assert normalised == ("role",)


def test_a_valid_two_entry_scope_returns_the_normalised_entries_in_scope_order(
    scope_validator: ScopeValidator,
) -> None:
    normalised = scope_validator.validate(
        kind=SCOPED_DEVICE_KIND, attribute_name=SCOPED_DEVICE_ATTRIBUTE, scope=["role__value", "site"]
    )

    assert normalised == ("role", "site")


@pytest.mark.parametrize("attribute_name", [SCOPED_DEVICE_ATTRIBUTE, UNIQUE_ATTRIBUTE])
def test_an_empty_scope_is_accepted_as_unscoped(scope_validator: ScopeValidator, attribute_name: str) -> None:
    assert scope_validator.validate(kind=SCOPED_DEVICE_KIND, attribute_name=attribute_name, scope=[]) == ()


@pytest.mark.parametrize("value", [[1], "site", ["site", 1], {"site": "value"}], ids=["int", "string", "mixed", "dict"])
def test_a_scope_that_is_not_a_list_of_strings_is_refused(value: object) -> None:
    with pytest.raises(ValidationError) as exc:
        ScopeValidator.parse(value=value)

    assert exc.value.message.endswith("at allocation_scope")
    assert "must be a list of field names" in exc.value.message


@pytest.mark.parametrize(
    ("value", "expected"), [(None, []), ([], []), (["site", "role__value"], ["site", "role__value"])]
)
def test_a_list_of_strings_or_null_is_parsed_as_the_scope_entries(value: object, expected: list[str]) -> None:
    assert ScopeValidator.parse(value=value) == expected


@pytest.mark.parametrize(("entry", "expected"), [("site", "site"), ("role__value", "role"), ("site__name", "site")])
def test_the_field_name_of_an_entry_drops_the_property_suffix(entry: str, expected: str) -> None:
    assert ScopeValidator.field_name(entry=entry) == expected
