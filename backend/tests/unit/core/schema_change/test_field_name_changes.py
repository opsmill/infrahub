from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema_change.field_name_changes import FieldNameChanges

ALPHA_ID = "6f0c3a52-8d1e-4b7a-9c2f-1e5d7a3b9c40"
BETA_ID = "0a9b8c7d-6e5f-4a3b-8c2d-1e0f9a8b7c6d"


def _node_with_alpha_and_beta() -> NodeSchema:
    return NodeSchema(
        name="Widget",
        namespace="Testing",
        attributes=[
            AttributeSchema(id=ALPHA_ID, name="alpha", kind="Text"),
            AttributeSchema(id=BETA_ID, name="beta", kind="Text"),
        ],
        human_friendly_id=["alpha__value"],
        order_by=["alpha__value"],
    )


def _swap_alpha_and_beta(node: NodeSchema, changes: FieldNameChanges) -> None:
    alpha = node.get_attribute(name="alpha")
    beta = node.get_attribute(name="beta")
    alpha.name = "beta"
    changes.rename(element=alpha, old_name="alpha", position=0)
    beta.name = "alpha"
    changes.rename(element=beta, old_name="beta", position=1)


def test_a_path_property_that_no_operation_set_takes_the_names_after_a_swap() -> None:
    node = _node_with_alpha_and_beta()
    changes = FieldNameChanges()
    _swap_alpha_and_beta(node=node, changes=changes)

    changes.rewrite_paths(node=node)

    assert node.human_friendly_id == ["beta__value"]
    assert node.order_by == ["beta__value"]


def test_a_path_property_that_an_operation_set_keeps_the_value_it_was_set_to() -> None:
    node = _node_with_alpha_and_beta()
    changes = FieldNameChanges()
    _swap_alpha_and_beta(node=node, changes=changes)
    node.order_by = ["alpha__value"]
    changes.set_property("order_by")

    changes.rewrite_paths(node=node)

    assert node.human_friendly_id == ["beta__value"]
    assert node.order_by == ["alpha__value"]
