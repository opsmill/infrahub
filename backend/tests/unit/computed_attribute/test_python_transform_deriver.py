from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from infrahub.computed_attribute.scoping import ComputedAttributeRef, PythonTransformDependencyDeriver
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema.schema_branch_computed import TransformReadSet

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


def test_display_label_read_marks_imprecise() -> None:
    read_set = TransformReadSet.from_read_fields({OWNER_KIND: {"name"}, "TestPerson": {"display_label"}})

    assert read_set.depends_on_everything is True


def test_hfid_read_marks_imprecise() -> None:
    read_set = TransformReadSet.from_read_fields({OWNER_KIND: {"hfid"}})

    assert read_set.depends_on_everything is True


def test_from_read_fields_precise() -> None:
    read_set = TransformReadSet.from_read_fields({OWNER_KIND: {"name", "owner"}, "TestPerson": {"name"}})

    assert read_set.depends_on_everything is False
    assert set(read_set.read_kinds) == {OWNER_KIND, "TestPerson"}
    assert {kind: set(fields) for kind, fields in read_set.read_fields.items()} == {
        OWNER_KIND: {"name", "owner"},
        "TestPerson": {"name"},
    }


def test_kind_with_no_mapped_fields_marks_imprecise() -> None:
    # The query analyzer drops reads it cannot map to a concrete schema element (such as a
    # human-friendly id read), leaving a traversed kind with an empty field set. That read
    # cannot be scoped, so the whole set must be imprecise rather than a precise read of nothing.
    read_set = TransformReadSet.from_read_fields({OWNER_KIND: set()})

    assert read_set.depends_on_everything is True
