from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.computed_attribute.scoping import ComputedAttributeRef, Jinja2DependencyDeriver
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema.schema_branch_computed import ComputedAttributeTriggerNode

OWNER_KIND = "TestComputeDevice"
PEER_KIND = "TestComputeOwner"


def _ref(attribute_name: str, kind: str = OWNER_KIND) -> ComputedAttributeRef:
    return ComputedAttributeRef(
        branch="main",
        kind=kind,
        attribute_name=attribute_name,
        computed_kind=ComputedAttributeKind.JINJA2,
    )


def _deriver(attribute_name: str, trigger_nodes: list[ComputedAttributeTriggerNode]) -> Jinja2DependencyDeriver:
    return Jinja2DependencyDeriver(trigger_nodes={(OWNER_KIND, attribute_name): trigger_nodes})


@dataclass
class DeriveCase:
    name: str
    attribute_name: str
    trigger_nodes: list[ComputedAttributeTriggerNode]
    expected_read_kinds: set[str]
    expected_read_fields: dict[str, set[str]]
    expected_depends_on_everything: bool = False


DERIVE_CASES = [
    DeriveCase(
        name="local_only_excludes_unrelated_kinds",
        attribute_name="local_label",
        trigger_nodes=[ComputedAttributeTriggerNode(kind=OWNER_KIND, attributes=["name", "role"], targets_self=True)],
        expected_read_kinds={OWNER_KIND},
        expected_read_fields={OWNER_KIND: {"name", "role", "local_label"}},
    ),
    DeriveCase(
        name="relationship_reached_peer_included",
        attribute_name="remote_label",
        trigger_nodes=[
            ComputedAttributeTriggerNode(kind=OWNER_KIND, attributes=["name", "owner"], targets_self=True),
            ComputedAttributeTriggerNode(kind=PEER_KIND, attributes=["name"], relationships=["owner"]),
        ],
        expected_read_kinds={OWNER_KIND, PEER_KIND},
        expected_read_fields={OWNER_KIND: {"name", "owner", "remote_label"}, PEER_KIND: {"name", "owner"}},
    ),
]


@pytest.mark.parametrize("case", DERIVE_CASES, ids=[c.name for c in DERIVE_CASES])
def test_derive(case: DeriveCase) -> None:
    attribute_name = case.attribute_name

    dependencies = _deriver(attribute_name, case.trigger_nodes).derive(computed_attribute=_ref(attribute_name))

    assert dependencies.owner_kind == OWNER_KIND
    assert dependencies.attribute_name == attribute_name
    assert dependencies.kind == ComputedAttributeKind.JINJA2
    assert dependencies.depends_on_everything is case.expected_depends_on_everything
    assert set(dependencies.read_kinds) == case.expected_read_kinds
    assert {kind: set(fields) for kind, fields in dependencies.read_fields.items()} == case.expected_read_fields


def test_own_definition_always_in_read_fields() -> None:
    deriver = _deriver(
        "local_label", [ComputedAttributeTriggerNode(kind=OWNER_KIND, attributes=["name"], targets_self=True)]
    )

    dependencies = deriver.derive(computed_attribute=_ref("local_label"))

    assert "local_label" in dependencies.read_fields[OWNER_KIND]
    assert OWNER_KIND in dependencies.read_kinds


def test_missing_trigger_nodes_depends_on_everything() -> None:
    deriver = Jinja2DependencyDeriver(trigger_nodes={})

    dependencies = deriver.derive(computed_attribute=_ref("local_label"))

    assert dependencies.depends_on_everything is True
    assert dependencies.read_kinds == frozenset({OWNER_KIND})


def test_display_label_read_marks_depends_on_everything() -> None:
    deriver = _deriver(
        "remote_label",
        [
            ComputedAttributeTriggerNode(kind=OWNER_KIND, attributes=["owner"], targets_self=True),
            ComputedAttributeTriggerNode(kind=PEER_KIND, attributes=["display_label"], relationships=["owner"]),
        ],
    )

    dependencies = deriver.derive(computed_attribute=_ref("remote_label"))

    assert dependencies.depends_on_everything is True


def test_hfid_read_marks_depends_on_everything() -> None:
    deriver = _deriver(
        "remote_label", [ComputedAttributeTriggerNode(kind=PEER_KIND, attributes=["hfid"], relationships=["owner"])]
    )

    dependencies = deriver.derive(computed_attribute=_ref("remote_label"))

    assert dependencies.depends_on_everything is True
