from __future__ import annotations

from infrahub.core.models import HashableModelDiff, SchemaDiff
from infrahub.events.schema_action import build_changed_elements_payload


def _attributes_bucket(
    *, added: list[str] | None = None, changed: list[str] | None = None, removed: list[str] | None = None
) -> HashableModelDiff:
    """A node diff that carries its attribute changes the way the schema diff nests them.

    Attribute and relationship changes are grouped under nested ``attributes`` /
    ``relationships`` buckets; the individual element names live one level down.
    """
    bucket = HashableModelDiff(
        added=dict.fromkeys(added or []),
        changed=dict.fromkeys(changed or []),
        removed=dict.fromkeys(removed or []),
    )
    return HashableModelDiff(changed={"attributes": bucket})


def test_changed_attribute_surfaces_field_name_not_bucket() -> None:
    diff = SchemaDiff(changed={"InfraDevice": _attributes_bucket(changed=["computed_description", "type"])})

    payload = build_changed_elements_payload(diff)

    assert payload.changed_fields == {"InfraDevice": ["computed_description", "type"]}
    assert "attributes" not in payload.changed_fields["InfraDevice"]


def test_relationship_bucket_surfaces_relationship_names() -> None:
    relationships = HashableModelDiff(changed={"provider": None})
    node_diff = HashableModelDiff(changed={"relationships": relationships})
    diff = SchemaDiff(changed={"InfraCircuit": node_diff})

    payload = build_changed_elements_payload(diff)

    assert payload.changed_fields == {"InfraCircuit": ["provider"]}


def test_added_changed_and_removed_elements_are_all_recorded() -> None:
    diff = SchemaDiff(
        changed={"InfraDevice": _attributes_bucket(added=["new_field"], changed=["type"], removed=["legacy"])}
    )

    payload = build_changed_elements_payload(diff)

    assert payload.changed_fields == {"InfraDevice": ["legacy", "new_field", "type"]}


def test_node_level_field_kept_under_its_own_name() -> None:
    node_diff = HashableModelDiff(changed={"label": None, "attributes": HashableModelDiff(changed={"type": None})})
    diff = SchemaDiff(changed={"InfraDevice": node_diff})

    payload = build_changed_elements_payload(diff)

    assert payload.changed_fields == {"InfraDevice": ["label", "type"]}


def test_added_and_removed_kinds_are_captured() -> None:
    diff = SchemaDiff(added={"NewKind": HashableModelDiff()}, removed={"OldKind": HashableModelDiff()})

    payload = build_changed_elements_payload(diff)

    assert payload.added_kinds == ["NewKind"]
    assert payload.removed_kinds == ["OldKind"]
    assert payload.changed_fields == {}
