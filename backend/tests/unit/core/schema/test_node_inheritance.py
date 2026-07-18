from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_inheritance_handler import NodeInheritanceHandler
from infrahub.core.schema.node_schema import NodeSchema


def _build_inheritance_setup(
    *,
    interface_attr_name: str,
    interface_attr_id: str,
    node_inherited_attr_name: str,
    node_order_by: list[str] | None = None,
) -> tuple[GenericSchema, NodeSchema]:
    interface = GenericSchema(
        name="Item",
        namespace="Testing",
        attributes=[AttributeSchema(name=interface_attr_name, kind="Text")],
    )
    interface.attributes[0].id = interface_attr_id

    node = NodeSchema(
        name="Note",
        namespace="Testing",
        attributes=[AttributeSchema(name=node_inherited_attr_name, kind="Text", inherited=True)],
        order_by=node_order_by,
    )
    node.attributes[0].source_attribute_id = interface_attr_id
    return interface, node


def test_inherit_renamed_attribute_preserves_metadata_order_by_entries() -> None:
    interface, node = _build_inheritance_setup(
        interface_attr_name="title",
        interface_attr_id="attr-title",
        node_inherited_attr_name="name",
        node_order_by=["node_metadata__created_at__desc", "name__value"],
    )

    NodeInheritanceHandler().inherit_from_interface(node=node, interface=interface)

    assert node.order_by == ["node_metadata__created_at__desc", "title__value"]


def test_inherit_renamed_attribute_only_metadata_entries_unchanged() -> None:
    interface, node = _build_inheritance_setup(
        interface_attr_name="title",
        interface_attr_id="attr-title",
        node_inherited_attr_name="name",
        node_order_by=["node_metadata__created_at", "node_metadata__updated_at__desc"],
    )

    NodeInheritanceHandler().inherit_from_interface(node=node, interface=interface)

    assert node.order_by == ["node_metadata__created_at", "node_metadata__updated_at__desc"]


def test_inherit_renamed_attribute_rewrites_direction_suffix_entries() -> None:
    interface, node = _build_inheritance_setup(
        interface_attr_name="title",
        interface_attr_id="attr-title",
        node_inherited_attr_name="name",
        node_order_by=["name__value__desc"],
    )

    NodeInheritanceHandler().inherit_from_interface(node=node, interface=interface)

    assert node.order_by == ["title__value__desc"]


def test_inherit_order_by_with_metadata_from_generic() -> None:
    generic = GenericSchema(
        name="Item",
        namespace="Testing",
        attributes=[AttributeSchema(name="name", kind="Text")],
        order_by=["node_metadata__created_at__desc"],
    )
    node = NodeSchema(
        name="Note",
        namespace="Testing",
        attributes=[AttributeSchema(name="name", kind="Text")],
    )

    NodeInheritanceHandler().inherit_from_interface(node=node, interface=generic)

    assert node.order_by == ["node_metadata__created_at__desc"]


def test_concrete_order_by_not_overridden_by_generic() -> None:
    generic = GenericSchema(
        name="Item",
        namespace="Testing",
        attributes=[AttributeSchema(name="name", kind="Text")],
        order_by=["node_metadata__created_at__desc"],
    )
    node = NodeSchema(
        name="Note",
        namespace="Testing",
        attributes=[AttributeSchema(name="name", kind="Text")],
        order_by=["name__value__asc"],
    )

    NodeInheritanceHandler().inherit_from_interface(node=node, interface=generic)

    assert node.order_by == ["name__value__asc"]
