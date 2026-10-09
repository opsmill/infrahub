from __future__ import annotations

import copy
import datetime
import re
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.exceptions import ValidationError
from infrahub.pools.scope import (
    AllocationScope,
    AllocationScopeResolver,
    AllocationScopeValidator,
    Division,
    ScopeElement,
    UnknownScopeElementError,
)
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_HOLDER,
    SCOPED_LINK,
    SCOPED_POD_HOLDER,
    SCOPED_POOL_SCHEMA,
    SCOPED_RACK,
    SCOPED_SITE,
)

SITE = ScopeElement(id="17d0a4c2-0000-4000-8000-000000000001", name="site")
ROLE = ScopeElement(id="3b1f90ee-0000-4000-8000-000000000002", name="role")


@dataclass(frozen=True)
class RefusedEntryCase:
    name: str
    entry: Any
    shown: str


@dataclass(frozen=True)
class DivisionValuesCase:
    name: str
    values: tuple[str | int, ...]


@dataclass(frozen=True)
class DistinctDivisionsCase:
    name: str
    first: tuple[str | int, ...]
    second: tuple[str | int, ...]


REFUSED_ENTRY_CASES = [
    RefusedEntryCase(name="plain-name", entry="site", shown='"site"'),
    RefusedEntryCase(name="missing-name", entry={"id": SITE.id}, shown=f'{{"id": "{SITE.id}"}}'),
    RefusedEntryCase(name="missing-id", entry={"name": "site"}, shown='{"name": "site"}'),
    RefusedEntryCase(name="id-not-text", entry={"id": 7, "name": "site"}, shown='{"id": 7, "name": "site"}'),
    RefusedEntryCase(name="name-not-text", entry={"id": SITE.id, "name": 3}, shown=f'{{"id": "{SITE.id}", "name": 3}}'),
    RefusedEntryCase(name="not-serializable", entry=datetime.date(2020, 1, 1), shown='"datetime.date(2020, 1, 1)"'),
]

DIVISION_VALUES_CASES = [
    DivisionValuesCase(name="scalar", values=("site-a-id",)),
    DivisionValuesCase(name="two-scalars", values=("site-a-id", "leaf")),
    DivisionValuesCase(name="number", values=(42,)),
    DivisionValuesCase(name="no-value", values=("",)),
]

DISTINCT_DIVISIONS_CASES = [
    DistinctDivisionsCase(name="scalar", first=("site-a-id",), second=("site-b-id",)),
    DistinctDivisionsCase(name="order", first=("site-a-id", "leaf"), second=("leaf", "site-a-id")),
    DistinctDivisionsCase(name="no-value-against-value", first=("",), second=("site-a-id",)),
    DistinctDivisionsCase(name="text-against-number", first=("1",), second=(1,)),
]


class TestAllocationScopeStoredForm:
    @pytest.mark.parametrize("stored", [None, []], ids=["absent", "empty"])
    def test_absent_or_empty_value_reads_as_unscoped(self, stored: list[Any] | None) -> None:
        scope = AllocationScope.from_stored(value=stored, pool="vlan-per-site")

        assert scope.is_empty
        assert scope.element_names == ()
        assert scope.to_stored() == []

    def test_stored_elements_read_back_in_order(self) -> None:
        stored = [{"id": ROLE.id, "name": "role"}, {"id": SITE.id, "name": "site"}]

        scope = AllocationScope.from_stored(value=stored, pool="vlan-per-site")

        assert scope.elements == (ROLE, SITE)
        assert not scope.is_empty
        assert scope.element_names == ("role", "site")
        assert scope.to_stored() == stored

    def test_scope_round_trips_through_its_stored_form(self) -> None:
        scope = AllocationScope(elements=(SITE, ROLE))

        assert AllocationScope.from_stored(value=scope.to_stored(), pool="vlan-per-site") == scope

    @pytest.mark.parametrize("case", REFUSED_ENTRY_CASES, ids=[case.name for case in REFUSED_ENTRY_CASES])
    def test_entry_that_is_not_an_element_is_refused_naming_the_pool(self, case: RefusedEntryCase) -> None:
        expected = (
            f"allocation_scope of pool vlan-per-site: the stored entry {case.shown} is not an element "
            'with an "id" and a "name"; recreate the pool to set its scope'
        )

        with pytest.raises(ValidationError, match=f"^{re.escape(expected)}$"):
            AllocationScope.from_stored(value=[{"id": ROLE.id, "name": "role"}, case.entry], pool="vlan-per-site")

    def test_stored_value_that_is_not_a_list_is_refused_naming_the_pool(self) -> None:
        expected = (
            'allocation_scope of pool vlan-per-site: the stored value "site" is not a list of elements; '
            "recreate the pool to set its scope"
        )

        with pytest.raises(ValidationError, match=f"^{re.escape(expected)}$"):
            AllocationScope.from_stored(value="site", pool="vlan-per-site")


class TestDivisionKey:
    @pytest.mark.parametrize("case", DIVISION_VALUES_CASES, ids=[case.name for case in DIVISION_VALUES_CASES])
    def test_equal_divisions_share_a_key(self, case: DivisionValuesCase) -> None:
        first = Division(values=case.values)
        second = Division(values=copy.deepcopy(case.values))

        assert first == second
        assert first.key == second.key
        assert {first, second} == {first}

    def test_key_of_a_value_holding_a_lone_surrogate_is_computed(self) -> None:
        # A text value can hold a lone surrogate, which UTF-8 cannot encode.
        division = Division(values=("\ud83d",))

        assert division.key != Division(values=("",)).key

    def test_key_is_the_same_in_every_process(self) -> None:
        division = Division(values=("site-a-id", "leaf", 42))

        assert division.key == "ee0417abeedcbfc0f9d05a07954f6dcf4f3941ebf2e1f013fdaefa3920abfaa3"

    @pytest.mark.parametrize("case", DISTINCT_DIVISIONS_CASES, ids=[case.name for case in DISTINCT_DIVISIONS_CASES])
    def test_different_divisions_have_different_keys(self, case: DistinctDivisionsCase) -> None:
        assert Division(values=case.first) != Division(values=case.second)
        assert Division(values=case.first).key != Division(values=case.second).key


DEVICE_KIND = SCOPED_DEVICE.kind
HOLDER_KIND = SCOPED_HOLDER.kind
POD_HOLDER_KIND = SCOPED_POD_HOLDER.kind
TRACKED_ATTRIBUTE = "vlan_id"
UNIQUE_ATTRIBUTE = "asset_number"
UNKNOWN_FIELD_ID = "unknown-field-id"


def _device_attributes_for_refusals() -> list[AttributeSchema]:
    """Return the device attributes that the shared test schema lacks, each to be refused as a scope element."""
    return [
        AttributeSchema(name="description", kind="Text", optional=True),
        AttributeSchema(name="settings", kind="JSON", optional=False),
        AttributeSchema(name="payload", kind="Any", optional=False),
        AttributeSchema(name=UNIQUE_ATTRIBUTE, kind="Number", optional=True, unique=True),
    ]


def _schema_branch(name: str, schema: SchemaRoot) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name=name)
    schema_branch.load_schema(schema=copy.deepcopy(schema))
    schema_branch.process()
    return schema_branch


def _field_id(kind: str, name: str) -> str:
    return f"{kind}-{name}-id"


def _with_field_ids[SchemaT: (NodeSchema, GenericSchema)](schema: SchemaT) -> SchemaT:
    """Return a copy of the schema whose own fields hold the ids a saved schema gives them."""
    saved: SchemaT = copy.deepcopy(schema)
    for attribute in saved.attributes:
        attribute.id = _field_id(kind=saved.kind, name=attribute.name)
    for relationship in saved.relationships:
        relationship.id = _field_id(kind=saved.kind, name=relationship.name)
    return saved


def _saved_scoped_schema(extra_device_attributes: list[AttributeSchema] | None = None) -> SchemaRoot:
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes.extend(extra_device_attributes or [])
    return SchemaRoot(
        generics=[_with_field_ids(SCOPED_HOLDER)],
        nodes=[SCOPED_SITE, SCOPED_RACK, SCOPED_LINK, _with_field_ids(device), _with_field_ids(SCOPED_POD_HOLDER)],
    )


@pytest.fixture
def saved_schema_branch() -> SchemaBranch:
    return _schema_branch(
        name="main", schema=_saved_scoped_schema(extra_device_attributes=_device_attributes_for_refusals())
    )


@pytest.fixture
def resolver(saved_schema_branch: SchemaBranch) -> AllocationScopeResolver:
    return AllocationScopeResolver(schema_branch=saved_schema_branch)


@pytest.fixture
def validator(saved_schema_branch: SchemaBranch) -> AllocationScopeValidator:
    return AllocationScopeValidator(schema_branch=saved_schema_branch)


def _resolve(resolver: AllocationScopeResolver, entries: object, kind: str = DEVICE_KIND) -> AllocationScope:
    return resolver.resolve(kind=kind, entries=entries)


def _element(name: str, kind: str = DEVICE_KIND) -> ScopeElement:
    return ScopeElement(id=_field_id(kind=kind, name=name), name=name)


@dataclass(frozen=True)
class AllocationScopeRefusalTestCase:
    name: str
    entries: object
    expected_message: str
    refused_on_lookup: bool
    """Whether the resolver refuses the entries, or only the validator does."""
    kind: str = DEVICE_KIND
    tracked_attribute: str = TRACKED_ATTRIBUTE


ALLOCATION_SCOPE_REFUSAL_TEST_CASES: list[AllocationScopeRefusalTestCase] = [
    AllocationScopeRefusalTestCase(
        name="unknown_name",
        refused_on_lookup=True,
        entries=["site", "zone"],
        expected_message=f'"zone" is not an attribute or a relationship of {DEVICE_KIND} on branch main',
    ),
    AllocationScopeRefusalTestCase(
        name="unknown_id",
        refused_on_lookup=True,
        entries=[{"id": UNKNOWN_FIELD_ID, "name": "site"}],
        expected_message=f'"{UNKNOWN_FIELD_ID}" is not an attribute or a relationship of {DEVICE_KIND} on branch main',
    ),
    AllocationScopeRefusalTestCase(
        name="optional_attribute",
        refused_on_lookup=False,
        entries=["description"],
        expected_message=f'"description" is optional; a scope element must be required on {DEVICE_KIND}',
    ),
    AllocationScopeRefusalTestCase(
        name="optional_relationship",
        refused_on_lookup=False,
        entries=["rack"],
        expected_message=f'"rack" is optional; a scope element must be required on {DEVICE_KIND}',
    ),
    AllocationScopeRefusalTestCase(
        name="cardinality_many",
        refused_on_lookup=False,
        entries=["links"],
        expected_message='"links" has cardinality many; a scope element must be a relationship of cardinality one',
    ),
    AllocationScopeRefusalTestCase(
        name="list_attribute",
        refused_on_lookup=False,
        entries=["tags"],
        expected_message='"tags" is of kind List; a scope element must hold a single scalar value',
    ),
    AllocationScopeRefusalTestCase(
        name="json_attribute",
        refused_on_lookup=False,
        entries=["settings"],
        expected_message='"settings" is of kind JSON; a scope element must hold a single scalar value',
    ),
    AllocationScopeRefusalTestCase(
        name="any_attribute",
        refused_on_lookup=False,
        entries=["payload"],
        expected_message='"payload" is of kind Any; a scope element must hold a single scalar value',
    ),
    AllocationScopeRefusalTestCase(
        name="path_into_peer",
        refused_on_lookup=True,
        entries=["site__name"],
        expected_message=(
            f'"site__name" is a path; a scope element must be an attribute or a relationship of {DEVICE_KIND} itself'
        ),
    ),
    AllocationScopeRefusalTestCase(
        name="path_into_property",
        refused_on_lookup=True,
        entries=["role__value"],
        expected_message=(
            f'"role__value" is a path; a scope element must be an attribute or a relationship of {DEVICE_KIND} itself'
        ),
    ),
    AllocationScopeRefusalTestCase(
        name="tracked_attribute",
        refused_on_lookup=False,
        entries=[TRACKED_ATTRIBUTE],
        expected_message=f'"{TRACKED_ATTRIBUTE}" is the attribute the pool allocates; it cannot divide the pool',
    ),
    AllocationScopeRefusalTestCase(
        name="duplicate_name",
        refused_on_lookup=False,
        entries=["site", "role", "site"],
        expected_message='"site" appears more than once',
    ),
    AllocationScopeRefusalTestCase(
        name="duplicate_by_name_and_id",
        refused_on_lookup=False,
        entries=["role", _field_id(kind=DEVICE_KIND, name="role")],
        expected_message='"role" appears more than once',
    ),
    AllocationScopeRefusalTestCase(
        name="generic_entry_declared_on_an_implementing_kind_only",
        refused_on_lookup=True,
        entries=["site", "pod"],
        kind=HOLDER_KIND,
        expected_message=f'"pod" is not declared on the generic {HOLDER_KIND}',
    ),
    AllocationScopeRefusalTestCase(
        name="unique_tracked_attribute",
        refused_on_lookup=False,
        entries=["site"],
        tracked_attribute=UNIQUE_ATTRIBUTE,
        expected_message=(
            f"{DEVICE_KIND}.{UNIQUE_ATTRIBUTE} is unique; a globally unique number cannot be allocated per division"
        ),
    ),
]


def _set_scope(
    resolver: AllocationScopeResolver, validator: AllocationScopeValidator, test_case: AllocationScopeRefusalTestCase
) -> AllocationScope:
    scope = resolver.resolve(kind=test_case.kind, entries=test_case.entries)
    validator.validate(kind=test_case.kind, tracked_attribute=test_case.tracked_attribute, scope=scope)
    return scope


@pytest.mark.parametrize("test_case", ALLOCATION_SCOPE_REFUSAL_TEST_CASES, ids=lambda test_case: test_case.name)
def test_setting_a_scope_refuses_an_entry_that_cannot_divide_the_pool(
    resolver: AllocationScopeResolver, validator: AllocationScopeValidator, test_case: AllocationScopeRefusalTestCase
) -> None:
    with pytest.raises(ValidationError) as exc:
        _set_scope(resolver=resolver, validator=validator, test_case=test_case)

    assert exc.value.message == f"{test_case.expected_message} at allocation_scope"


@pytest.mark.parametrize(
    "test_case",
    [test_case for test_case in ALLOCATION_SCOPE_REFUSAL_TEST_CASES if not test_case.refused_on_lookup],
    ids=lambda test_case: test_case.name,
)
def test_the_resolver_returns_the_elements_that_only_the_validator_refuses(
    resolver: AllocationScopeResolver, test_case: AllocationScopeRefusalTestCase
) -> None:
    assert isinstance(test_case.entries, list)

    scope = resolver.resolve(kind=test_case.kind, entries=test_case.entries)

    assert len(scope.elements) == len(test_case.entries)


@pytest.mark.parametrize(
    "test_case",
    [test_case for test_case in ALLOCATION_SCOPE_REFUSAL_TEST_CASES if test_case.refused_on_lookup],
    ids=lambda test_case: test_case.name,
)
def test_the_resolver_refuses_an_entry_that_names_no_element_as_unknown(
    resolver: AllocationScopeResolver, test_case: AllocationScopeRefusalTestCase
) -> None:
    with pytest.raises(UnknownScopeElementError):
        resolver.resolve(kind=test_case.kind, entries=test_case.entries)


@pytest.mark.parametrize(
    "entries",
    ["site", {"id": "site"}, [1], ["site", None], [{"name": "site"}], [{"id": 1, "name": "site"}]],
    ids=["string", "object", "int", "none-entry", "object-without-id", "id-not-a-string"],
)
def test_the_resolver_refuses_entries_that_are_not_a_list_of_names_ids_or_objects(
    resolver: AllocationScopeResolver, entries: object
) -> None:
    with pytest.raises(ValidationError) as exc:
        _resolve(resolver=resolver, entries=entries)

    assert exc.value.message == "the allocation scope must be a list of entries at allocation_scope"
    assert not isinstance(exc.value, UnknownScopeElementError)


def test_the_resolver_refuses_a_kind_the_schema_does_not_define(resolver: AllocationScopeResolver) -> None:
    with pytest.raises(ValidationError) as exc:
        _resolve(resolver=resolver, entries=["site"], kind="ScopeGone")

    assert exc.value.message == "ScopeGone is not defined on branch main at allocation_scope"
    assert not isinstance(exc.value, UnknownScopeElementError)


def test_the_resolver_refuses_an_element_whose_schema_is_not_saved() -> None:
    resolver = AllocationScopeResolver(schema_branch=_schema_branch(name="main", schema=SCOPED_POOL_SCHEMA))

    with pytest.raises(ValidationError) as exc:
        _resolve(resolver=resolver, entries=["role"])

    assert exc.value.message == (
        f'"role" has no id; the schema of {DEVICE_KIND} is not saved on branch main at allocation_scope'
    )


@pytest.mark.parametrize(
    "entries",
    [
        ["site", "role"],
        [_field_id(kind=DEVICE_KIND, name="site"), _field_id(kind=DEVICE_KIND, name="role")],
        [
            {"id": _field_id(kind=DEVICE_KIND, name="site"), "name": "site"},
            {"id": _field_id(kind=DEVICE_KIND, name="role"), "name": "stale-name"},
        ],
        ["site", {"id": _field_id(kind=DEVICE_KIND, name="role"), "name": "role"}],
    ],
    ids=["by-name", "by-id", "by-object", "mixed"],
)
def test_the_resolver_accepts_an_entry_by_name_by_id_or_by_object(
    resolver: AllocationScopeResolver, entries: list[object]
) -> None:
    scope = _resolve(resolver=resolver, entries=entries)

    assert scope.elements == (_element(name="site"), _element(name="role"))


def test_the_resolver_keeps_the_entry_order(resolver: AllocationScopeResolver) -> None:
    scope = _resolve(resolver=resolver, entries=["role", "name", "site"])

    assert scope.element_names == ("role", "name", "site")


@pytest.mark.parametrize("entries", [None, []], ids=["null", "empty-list"])
def test_the_resolver_reads_no_entry_as_an_unscoped_pool(resolver: AllocationScopeResolver, entries: object) -> None:
    assert _resolve(resolver=resolver, entries=entries).is_empty


def test_the_validator_accepts_no_element_on_a_pool_whose_attribute_is_unique(
    validator: AllocationScopeValidator,
) -> None:
    validator.validate(kind=DEVICE_KIND, tracked_attribute=UNIQUE_ATTRIBUTE, scope=AllocationScope())


def test_the_validator_accepts_required_scalar_elements(validator: AllocationScopeValidator) -> None:
    scope = AllocationScope(elements=(_element(name="site"), _element(name="role")))

    validator.validate(kind=DEVICE_KIND, tracked_attribute=TRACKED_ATTRIBUTE, scope=scope)


def test_the_resolver_accepts_an_element_the_generic_declares_on_a_pool_over_the_generic(
    resolver: AllocationScopeResolver, validator: AllocationScopeValidator
) -> None:
    scope = _resolve(resolver=resolver, entries=["site", "name"], kind=HOLDER_KIND)
    validator.validate(kind=HOLDER_KIND, tracked_attribute=TRACKED_ATTRIBUTE, scope=scope)

    assert scope.elements == (_element(name="site", kind=HOLDER_KIND), _element(name="name", kind=HOLDER_KIND))


def test_the_resolver_identifies_an_inherited_element_by_the_generic_id(resolver: AllocationScopeResolver) -> None:
    scope = _resolve(resolver=resolver, entries=["site", "pod"], kind=POD_HOLDER_KIND)

    assert scope.elements == (_element(name="site", kind=HOLDER_KIND), _element(name="pod", kind=POD_HOLDER_KIND))


def test_refresh_names_follows_a_renamed_element_and_keeps_an_unknown_one() -> None:
    schema = _saved_scoped_schema()
    device = next(node for node in schema.nodes if node.kind == DEVICE_KIND)
    device.get_attribute(name="role").name = "function"
    resolver = AllocationScopeResolver(schema_branch=_schema_branch(name="main", schema=schema))
    unknown = ScopeElement(id=UNKNOWN_FIELD_ID, name="zone")
    scope = AllocationScope(elements=(_element(name="site"), _element(name="role"), unknown))

    refreshed = resolver.refresh_names(scope=scope, kind=DEVICE_KIND)

    assert refreshed.elements == (
        _element(name="site"),
        ScopeElement(id=_field_id(kind=DEVICE_KIND, name="role"), name="function"),
        unknown,
    )


def test_refresh_names_follows_a_generic_element_renamed_on_an_implementing_kind() -> None:
    schema = _saved_scoped_schema()
    schema.generics[0].get_relationship(name="site").name = "location"
    resolver = AllocationScopeResolver(schema_branch=_schema_branch(name="main", schema=schema))
    scope = AllocationScope(elements=(_element(name="site", kind=HOLDER_KIND),))

    refreshed = resolver.refresh_names(scope=scope, kind=POD_HOLDER_KIND)

    assert refreshed.element_names == ("location",)
