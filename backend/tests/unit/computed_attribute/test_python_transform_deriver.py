from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.scoping import ComputedAttributeRef, PythonTransformDependencyDeriver
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema.derived_path import DerivedPathResolver
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema.schema_branch_computed import TransformReadSet
from infrahub.core.schema.schema_branch_computed.python_transform import (
    IMPRECISE_READ_FIELDS,
    derived_read_is_scopable,
)
from tests.helpers.schema.car import CAR
from tests.helpers.schema.person import PERSON


def _scopable_resolver() -> DerivedPathResolver:
    branch = SchemaBranch(cache={}, name="test")
    branch.set(name=CAR.kind, schema=CAR)
    branch.set(name=PERSON.kind, schema=PERSON)
    return DerivedPathResolver(schema_branch=branch)


if TYPE_CHECKING:
    from infrahub.core.schema import NodeSchema

BRANCH = "main"
OWNER_KIND = "TestCar"
ATTRIBUTE_NAME = "computed_desc_python"


def _ref(branch: str = BRANCH, kind: str = OWNER_KIND, attribute_name: str = ATTRIBUTE_NAME) -> ComputedAttributeRef:
    return ComputedAttributeRef(
        branch=branch,
        kind=kind,
        attribute_name=attribute_name,
        computed_kind=ComputedAttributeKind.TRANSFORM_PYTHON,
    )


@dataclass
class DeriveCase:
    name: str
    read_sets: dict[tuple[str, str, str], TransformReadSet]
    expected_depends_on_everything: bool
    expected_read_kinds: set[str] = field(default_factory=set)
    expected_read_fields: dict[str, set[str]] = field(default_factory=dict)
    expected_imprecise_kinds: set[str] = field(default_factory=set)


DERIVE_CASES = [
    DeriveCase(
        name="query_read_set_excludes_unrelated",
        read_sets={
            (BRANCH, OWNER_KIND, ATTRIBUTE_NAME): TransformReadSet(
                read_kinds=frozenset({OWNER_KIND}),
                read_fields={OWNER_KIND: frozenset({"name"})},
            )
        },
        expected_depends_on_everything=False,
        expected_read_kinds={OWNER_KIND},
        expected_read_fields={OWNER_KIND: {"name", ATTRIBUTE_NAME}},
    ),
    DeriveCase(
        name="related_kind_read_set",
        read_sets={
            (BRANCH, OWNER_KIND, ATTRIBUTE_NAME): TransformReadSet(
                read_kinds=frozenset({OWNER_KIND, "TestPerson"}),
                read_fields={OWNER_KIND: frozenset({"name", "owner"}), "TestPerson": frozenset({"name"})},
            )
        },
        expected_depends_on_everything=False,
        expected_read_kinds={OWNER_KIND, "TestPerson"},
        expected_read_fields={OWNER_KIND: {"name", "owner", ATTRIBUTE_NAME}, "TestPerson": {"name"}},
    ),
    DeriveCase(
        name="derived_read_is_carried_per_kind",
        read_sets={
            (BRANCH, OWNER_KIND, ATTRIBUTE_NAME): TransformReadSet.from_read_fields(
                {OWNER_KIND: {"name"}, "TestPerson": {"human_friendly_id"}},
                scopable_derived_kinds={"TestPerson"},
            )
        },
        expected_depends_on_everything=False,
        expected_read_kinds={OWNER_KIND, "TestPerson"},
        expected_read_fields={OWNER_KIND: {"name", ATTRIBUTE_NAME}},
        expected_imprecise_kinds={"TestPerson"},
    ),
    DeriveCase(
        name="unanalyzable_query_depends_on_everything",
        read_sets={(BRANCH, OWNER_KIND, ATTRIBUTE_NAME): TransformReadSet.imprecise()},
        expected_depends_on_everything=True,
    ),
    DeriveCase(
        name="missing_read_set_depends_on_everything",
        read_sets={},
        expected_depends_on_everything=True,
    ),
]


@pytest.mark.parametrize("case", DERIVE_CASES, ids=[c.name for c in DERIVE_CASES])
def test_derive(case: DeriveCase) -> None:
    deriver = PythonTransformDependencyDeriver(read_sets=case.read_sets)

    dependencies = deriver.derive(computed_attribute=_ref())

    assert dependencies.owner_kind == OWNER_KIND
    assert dependencies.attribute_name == ATTRIBUTE_NAME
    assert dependencies.kind == ComputedAttributeKind.TRANSFORM_PYTHON
    assert dependencies.depends_on_everything is case.expected_depends_on_everything

    if not case.expected_depends_on_everything:
        assert set(dependencies.read_kinds) == case.expected_read_kinds
        assert {kind: set(fields) for kind, fields in dependencies.read_fields.items()} == case.expected_read_fields
        assert set(dependencies.imprecise_kinds) == case.expected_imprecise_kinds


def test_own_definition_always_in_read_fields() -> None:
    deriver = PythonTransformDependencyDeriver(
        read_sets={
            (BRANCH, OWNER_KIND, ATTRIBUTE_NAME): TransformReadSet(
                read_kinds=frozenset({OWNER_KIND}),
                read_fields={OWNER_KIND: frozenset({"name"})},
            )
        }
    )

    dependencies = deriver.derive(computed_attribute=_ref())

    assert ATTRIBUTE_NAME in dependencies.read_fields[OWNER_KIND]
    assert OWNER_KIND in dependencies.read_kinds


def test_read_set_is_branch_specific() -> None:
    # The same computed attribute on two branches can have divergent transform queries; the
    # read set must be resolved for the candidate's own branch, never another branch's.
    deriver = PythonTransformDependencyDeriver(
        read_sets={
            (BRANCH, OWNER_KIND, ATTRIBUTE_NAME): TransformReadSet(
                read_kinds=frozenset({OWNER_KIND}), read_fields={OWNER_KIND: frozenset({"name"})}
            ),
            ("branch2", OWNER_KIND, ATTRIBUTE_NAME): TransformReadSet(
                read_kinds=frozenset({OWNER_KIND}), read_fields={OWNER_KIND: frozenset({"color"})}
            ),
        }
    )

    main_deps = deriver.derive(computed_attribute=_ref(branch=BRANCH))
    branch_deps = deriver.derive(computed_attribute=_ref(branch="branch2"))

    assert main_deps.read_fields[OWNER_KIND] == frozenset({"name", ATTRIBUTE_NAME})
    assert branch_deps.read_fields[OWNER_KIND] == frozenset({"color", ATTRIBUTE_NAME})


@pytest.mark.parametrize("derived_field", sorted(IMPRECISE_READ_FIELDS))
def test_a_derived_read_marks_only_its_own_kind_imprecise(derived_field: str) -> None:
    read_set = TransformReadSet.from_read_fields(
        {OWNER_KIND: {"name"}, "TestPerson": {derived_field}}, scopable_derived_kinds={"TestPerson"}
    )

    assert read_set.depends_on_everything is False
    assert set(read_set.imprecise_kinds) == {"TestPerson"}
    assert set(read_set.read_kinds) == {OWNER_KIND, "TestPerson"}
    assert {kind: set(fields) for kind, fields in read_set.read_fields.items()} == {OWNER_KIND: {"name"}}


def test_derived_read_on_an_unscopable_kind_collapses_the_whole_set() -> None:
    # A derived definition that crosses a relationship reads a peer's attribute, so a change to
    # that peer moves the value with nothing changing on the kind itself.
    read_set = TransformReadSet.from_read_fields({OWNER_KIND: {"name"}, "TestPerson": {"human_friendly_id"}})

    assert read_set.depends_on_everything is True
    assert set(read_set.imprecise_kinds) == set()
    assert read_set.read_fields == {}


def test_one_unscopable_derived_read_collapses_a_scopable_one_too() -> None:
    read_set = TransformReadSet.from_read_fields(
        {OWNER_KIND: {"display_label"}, "TestPerson": {"human_friendly_id"}},
        scopable_derived_kinds={OWNER_KIND},
    )

    assert read_set.depends_on_everything is True


def test_from_read_fields_precise() -> None:
    read_set = TransformReadSet.from_read_fields({OWNER_KIND: {"name", "owner"}, "TestPerson": {"name"}})

    assert read_set.depends_on_everything is False
    assert set(read_set.read_kinds) == {OWNER_KIND, "TestPerson"}
    assert {kind: set(fields) for kind, fields in read_set.read_fields.items()} == {
        OWNER_KIND: {"name", "owner"},
        "TestPerson": {"name"},
    }


def test_kind_with_no_mapped_fields_is_kind_only() -> None:
    # Traversing a relationship to a generic reports every member kind, including the ones
    # the query reads nothing from. Those stay a kind-level dependency only.
    read_set = TransformReadSet.from_read_fields(
        {
            "TestPerson": {"name", "cars"},
            "TestElectricCar": {"nbr_engine"},
            OWNER_KIND: set(),
            "TestGazCar": set(),
        }
    )

    assert read_set.depends_on_everything is False
    assert set(read_set.read_kinds) == {"TestPerson", "TestElectricCar", OWNER_KIND, "TestGazCar"}
    assert {kind: set(fields) for kind, fields in read_set.read_fields.items()} == {
        "TestPerson": {"name", "cars"},
        "TestElectricCar": {"nbr_engine"},
    }


def _car_with(**overrides: object) -> NodeSchema:
    car = deepcopy(CAR)
    for name, value in overrides.items():
        setattr(car, name, value)
    return car


@dataclass
class ScopableCase:
    name: str
    node_schema: NodeSchema
    field_name: str
    expected: bool


SCOPABLE_CASES = [
    ScopableCase(
        name="display_label_template_reads_own_attributes",
        node_schema=CAR,
        field_name="display_label",
        expected=True,
    ),
    ScopableCase(
        name="display_label_plain_path_reads_own_attribute",
        node_schema=PERSON,
        field_name="display_label",
        expected=True,
    ),
    ScopableCase(
        name="hfid_reads_own_attribute",
        node_schema=_car_with(human_friendly_id=["name__value"]),
        field_name="human_friendly_id",
        expected=True,
    ),
    ScopableCase(
        name="hfid_crossing_a_relationship",
        node_schema=_car_with(human_friendly_id=["owner__name__value", "name__value"]),
        field_name="human_friendly_id",
        expected=False,
    ),
    ScopableCase(
        name="display_label_path_crossing_a_relationship",
        node_schema=_car_with(display_label="owner__name__value"),
        field_name="display_label",
        expected=False,
    ),
    ScopableCase(
        name="display_label_template_crossing_a_relationship",
        node_schema=_car_with(display_label="{{ owner__name__value }}"),
        field_name="display_label",
        expected=False,
    ),
    ScopableCase(
        name="hfid_without_a_definition",
        node_schema=CAR,
        field_name="human_friendly_id",
        expected=False,
    ),
    ScopableCase(
        name="display_label_without_a_definition",
        node_schema=_car_with(display_label=None),
        field_name="display_label",
        expected=False,
    ),
    ScopableCase(
        name="path_naming_no_known_field",
        node_schema=_car_with(human_friendly_id=["not_a_field__value"]),
        field_name="human_friendly_id",
        expected=False,
    ),
]


@pytest.mark.parametrize("case", SCOPABLE_CASES, ids=[c.name for c in SCOPABLE_CASES])
def test_derived_read_is_scopable(case: ScopableCase) -> None:
    result = derived_read_is_scopable(
        path_resolver=_scopable_resolver(), node_schema=case.node_schema, field_name=case.field_name
    )
    assert result is case.expected


def test_derived_read_is_scopable_rejects_a_plain_field() -> None:
    with pytest.raises(ValueError, match=r"^name is not a derived node property of TestingCar$"):
        derived_read_is_scopable(path_resolver=_scopable_resolver(), node_schema=CAR, field_name="name")
