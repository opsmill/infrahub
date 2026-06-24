from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.scoping import (
    ChangedElementSet,
    ComputedAttributeRef,
    DependencySet,
    RecomputeScoper,
)
from infrahub.core.constants import ComputedAttributeKind

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class CannedDeriver:
    """Returns a pre-built dependency set per attribute name; ignores schema_branch."""

    def __init__(self, dependencies: Mapping[str, DependencySet]) -> None:
        self._dependencies = dependencies

    def derive(
        self,
        *,
        computed_attribute: ComputedAttributeRef,
    ) -> DependencySet:
        return self._dependencies[computed_attribute.attribute_name]


def _ref(attribute_name: str, kind: str = "TestingDevice") -> ComputedAttributeRef:
    return ComputedAttributeRef(
        branch="main",
        kind=kind,
        attribute_name=attribute_name,
        computed_kind=ComputedAttributeKind.JINJA2,
    )


def _dependency(
    *,
    owner_kind: str = "TestingDevice",
    attribute_name: str,
    read_kinds: frozenset[str] = frozenset(),
    read_fields: Mapping[str, frozenset[str]] | None = None,
    depends_on_everything: bool = False,
) -> DependencySet:
    return DependencySet(
        owner_kind=owner_kind,
        attribute_name=attribute_name,
        kind=ComputedAttributeKind.JINJA2,
        read_kinds=read_kinds,
        read_fields=read_fields or {},
        depends_on_everything=depends_on_everything,
    )


def _scoper(dependencies: Mapping[str, DependencySet]) -> RecomputeScoper:
    deriver = CannedDeriver(dependencies=dependencies)
    return RecomputeScoper(
        derivers={
            ComputedAttributeKind.JINJA2: deriver,
            ComputedAttributeKind.TRANSFORM_PYTHON: deriver,
        }
    )


@dataclass
class ScopeCase:
    name: str
    dependencies: Mapping[str, DependencySet]
    candidates: Sequence[ComputedAttributeRef]
    changed_elements: ChangedElementSet | None
    expected_selected_names: set[str]
    expected_fallback: bool
    expected_skipped_names: set[str] = field(default_factory=set)


SCOPE_CASES = [
    ScopeCase(
        name="hit_via_read_fields",
        dependencies={
            "full_name": _dependency(
                attribute_name="full_name",
                read_fields={"TestingDevice": frozenset({"hostname"})},
            ),
        },
        candidates=[_ref("full_name")],
        changed_elements=ChangedElementSet(changed_fields={"TestingDevice": frozenset({"hostname"})}),
        expected_selected_names={"full_name"},
        expected_fallback=False,
    ),
    ScopeCase(
        name="hit_via_read_kinds_intersect_added",
        dependencies={
            "site_label": _dependency(
                attribute_name="site_label",
                read_kinds=frozenset({"TestingSite"}),
            ),
        },
        candidates=[_ref("site_label")],
        changed_elements=ChangedElementSet(added_kinds=frozenset({"TestingSite"})),
        expected_selected_names={"site_label"},
        expected_fallback=False,
    ),
    ScopeCase(
        name="hit_via_read_kinds_intersect_removed",
        dependencies={
            "site_label": _dependency(
                attribute_name="site_label",
                read_kinds=frozenset({"TestingSite"}),
            ),
        },
        candidates=[_ref("site_label")],
        changed_elements=ChangedElementSet(removed_kinds=frozenset({"TestingSite"})),
        expected_selected_names={"site_label"},
        expected_fallback=False,
    ),
    ScopeCase(
        name="hit_via_own_definition_edit",
        dependencies={
            "full_name": _dependency(
                attribute_name="full_name",
                read_fields={"TestingDevice": frozenset({"hostname"})},
            ),
        },
        candidates=[_ref("full_name")],
        changed_elements=ChangedElementSet(changed_fields={"TestingDevice": frozenset({"full_name"})}),
        expected_selected_names={"full_name"},
        expected_fallback=False,
    ),
    ScopeCase(
        name="skip_when_no_overlap",
        dependencies={
            "full_name": _dependency(
                attribute_name="full_name",
                read_kinds=frozenset({"TestingDevice"}),
                read_fields={"TestingDevice": frozenset({"hostname"})},
            ),
        },
        candidates=[_ref("full_name")],
        changed_elements=ChangedElementSet(changed_fields={"TestingOther": frozenset({"unrelated"})}),
        expected_selected_names=set(),
        expected_skipped_names={"full_name"},
        expected_fallback=False,
    ),
    ScopeCase(
        name="depends_on_everything_selected_without_escalation",
        dependencies={
            "opaque": _dependency(attribute_name="opaque", depends_on_everything=True),
            "scoped": _dependency(
                attribute_name="scoped",
                read_fields={"TestingDevice": frozenset({"hostname"})},
            ),
        },
        candidates=[_ref("opaque"), _ref("scoped")],
        changed_elements=ChangedElementSet(changed_fields={"TestingOther": frozenset({"unrelated"})}),
        expected_selected_names={"opaque"},
        expected_skipped_names={"scoped"},
        expected_fallback=False,
    ),
    ScopeCase(
        name="changed_elements_none_full_recompute",
        dependencies={
            "full_name": _dependency(
                attribute_name="full_name",
                read_fields={"TestingDevice": frozenset({"hostname"})},
            ),
            "site_label": _dependency(
                attribute_name="site_label",
                read_kinds=frozenset({"TestingSite"}),
            ),
        },
        candidates=[_ref("full_name"), _ref("site_label")],
        changed_elements=None,
        expected_selected_names={"full_name", "site_label"},
        expected_fallback=True,
    ),
]


@pytest.mark.parametrize("case", SCOPE_CASES, ids=[c.name for c in SCOPE_CASES])
def test_scope(case: ScopeCase) -> None:
    scoper = _scoper(case.dependencies)

    report = scoper.scope(
        candidate_attributes=case.candidates,
        changed_elements=case.changed_elements,
    )

    selected_names = {ref.attribute_name for ref in report.selected}
    skipped_names = {skipped.ref.attribute_name for skipped in report.skipped}

    assert selected_names == case.expected_selected_names
    assert skipped_names == case.expected_skipped_names
    assert report.fallback_full_recompute is case.expected_fallback


def test_depends_on_everything_does_not_set_fallback() -> None:
    scoper = _scoper(
        {
            "opaque": _dependency(attribute_name="opaque", depends_on_everything=True),
            "scoped": _dependency(
                attribute_name="scoped",
                read_fields={"TestingDevice": frozenset({"hostname"})},
            ),
        }
    )

    report = scoper.scope(
        candidate_attributes=[_ref("opaque"), _ref("scoped")],
        changed_elements=ChangedElementSet(changed_fields={"TestingOther": frozenset({"unrelated"})}),
    )

    assert [ref.attribute_name for ref in report.selected] == ["opaque"]
    assert [skipped.ref.attribute_name for skipped in report.skipped] == ["scoped"]
    assert report.fallback_full_recompute is False


def test_selected_and_skipped_disjoint_and_complete() -> None:
    scoper = _scoper(
        {
            "selected_field": _dependency(
                attribute_name="selected_field",
                read_fields={"TestingDevice": frozenset({"hostname"})},
            ),
            "selected_kind": _dependency(
                attribute_name="selected_kind",
                read_kinds=frozenset({"TestingSite"}),
            ),
            "selected_everything": _dependency(attribute_name="selected_everything", depends_on_everything=True),
            "skipped_one": _dependency(
                attribute_name="skipped_one",
                read_fields={"TestingDevice": frozenset({"serial"})},
            ),
            "skipped_two": _dependency(
                attribute_name="skipped_two",
                read_kinds=frozenset({"TestingUnrelated"}),
            ),
        }
    )
    candidates = [
        _ref("selected_field"),
        _ref("selected_kind"),
        _ref("selected_everything"),
        _ref("skipped_one"),
        _ref("skipped_two"),
    ]

    report = scoper.scope(
        candidate_attributes=candidates,
        changed_elements=ChangedElementSet(
            added_kinds=frozenset({"TestingSite"}),
            changed_fields={"TestingDevice": frozenset({"hostname"})},
        ),
    )

    selected_refs = set(report.selected)
    skipped_refs = {skipped.ref for skipped in report.skipped}

    assert selected_refs.isdisjoint(skipped_refs)
    assert selected_refs | skipped_refs == set(candidates)
    assert len(report.selected) + len(report.skipped) == len(candidates)
    assert all(skipped.reason for skipped in report.skipped)
