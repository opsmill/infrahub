from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.attribute_schema import TextAttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.candidate_comparer import SchemaCandidateComparer
from tests.constants import TestKind

CABLE_KIND = "TestingCable"
DESCRIPTION_MAX_LENGTH = 128
"""The longest description that a kind accepts when it is parsed."""


def _with_device_attribute(schema: SchemaBranch, attribute: AttributeSchema) -> SchemaBranch:
    changed = schema.duplicate()
    device = changed.get(name=TestKind.DEVICE)
    device.attributes.append(attribute)
    changed.set(name=TestKind.DEVICE, schema=device)
    return changed


def test_two_equal_schemas_give_no_kind(equivalence_base_schema: SchemaBranch) -> None:
    differing_kinds = SchemaCandidateComparer().differing_kinds(
        direct_load_schema=equivalence_base_schema, applied_schema=equivalence_base_schema.duplicate()
    )

    assert differing_kinds == []


def test_a_changed_kind_and_a_kind_of_one_schema_only_are_returned_in_sorted_order(
    equivalence_base_schema: SchemaBranch,
) -> None:
    applied_schema = equivalence_base_schema.duplicate()
    tag = applied_schema.get(name=TestKind.TAG)
    tag.label = "Label"
    applied_schema.set(name=TestKind.TAG, schema=tag)
    applied_schema.set(name=CABLE_KIND, schema=NodeSchema(name="Cable", namespace="Testing", label="Cable"))

    differing_kinds = SchemaCandidateComparer().differing_kinds(
        direct_load_schema=equivalence_base_schema, applied_schema=applied_schema
    )

    assert differing_kinds == [CABLE_KIND, TestKind.TAG]


def test_an_attribute_with_the_same_content_in_another_class_gives_no_kind(
    equivalence_base_schema: SchemaBranch,
) -> None:
    direct_load_schema = _with_device_attribute(
        equivalence_base_schema, AttributeSchema(name="serial", kind="Text", optional=True)
    )
    applied_schema = _with_device_attribute(
        equivalence_base_schema, TextAttributeSchema(name="serial", kind="Text", optional=True)
    )
    assert direct_load_schema.to_dict()["nodes"][TestKind.DEVICE] != applied_schema.to_dict()["nodes"][TestKind.DEVICE]

    differing_kinds = SchemaCandidateComparer().differing_kinds(
        direct_load_schema=direct_load_schema, applied_schema=applied_schema
    )

    assert differing_kinds == []


def test_an_attribute_with_another_content_in_another_class_is_returned(
    equivalence_base_schema: SchemaBranch,
) -> None:
    direct_load_schema = _with_device_attribute(
        equivalence_base_schema, AttributeSchema(name="serial", kind="Text", optional=True)
    )
    applied_schema = _with_device_attribute(
        equivalence_base_schema, TextAttributeSchema(name="serial", kind="Text", optional=False)
    )

    differing_kinds = SchemaCandidateComparer().differing_kinds(
        direct_load_schema=direct_load_schema, applied_schema=applied_schema
    )

    assert differing_kinds == [TestKind.DEVICE]


def test_a_kind_that_cannot_be_parsed_again_is_returned(equivalence_base_schema: SchemaBranch) -> None:
    applied_schema = equivalence_base_schema.duplicate()
    tag = applied_schema.get(name=TestKind.TAG)
    tag.description = "x" * (DESCRIPTION_MAX_LENGTH + 1)
    applied_schema.set(name=TestKind.TAG, schema=tag)

    differing_kinds = SchemaCandidateComparer().differing_kinds(
        direct_load_schema=equivalence_base_schema, applied_schema=applied_schema
    )

    assert differing_kinds == [TestKind.TAG]
