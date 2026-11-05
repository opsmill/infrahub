from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.container import ContainerSchema
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


def _generic_with_containers(name: str, containers: list[ContainerSchema]) -> GenericSchema:
    return GenericSchema(
        name=name,
        namespace="Testing",
        containers=containers,
        attributes=[AttributeSchema(name="name", kind="Text", container="lacp")],
    )


def test_node_without_containers_receives_the_generic_containers() -> None:
    generic = _generic_with_containers(
        name="Item",
        containers=[
            ContainerSchema(name="lacp", label="LACP", order_weight=100),
            ContainerSchema(name="layer2", label="Layer 2", description="Switching", collapsed=True),
        ],
    )
    node = NodeSchema(name="Note", namespace="Testing")

    NodeInheritanceHandler().inherit_containers(node=node, interfaces=[generic])

    assert node.containers == [
        ContainerSchema(name="lacp", label="LACP", order_weight=100, inherited=True),
        ContainerSchema(name="layer2", label="Layer 2", description="Switching", collapsed=True, inherited=True),
    ]


def test_node_container_replaces_the_generic_container_of_the_same_name_only() -> None:
    generic = _generic_with_containers(
        name="Item",
        containers=[
            ContainerSchema(name="lacp", label="LACP", order_weight=100),
            ContainerSchema(name="layer2", label="Layer 2", order_weight=200),
        ],
    )
    node = NodeSchema(
        name="Note",
        namespace="Testing",
        containers=[ContainerSchema(name="layer2", label="Switching", collapsed=True)],
    )

    NodeInheritanceHandler().inherit_containers(node=node, interfaces=[generic])

    assert node.containers == [
        ContainerSchema(name="lacp", label="LACP", order_weight=100, inherited=True),
        ContainerSchema(name="layer2", label="Switching", collapsed=True),
    ]


def test_first_generic_wins_when_two_generics_declare_the_same_container() -> None:
    first = _generic_with_containers(name="Item", containers=[ContainerSchema(name="lacp", label="LACP")])
    second = _generic_with_containers(
        name="Bundle", containers=[ContainerSchema(name="lacp", label="Link aggregation", order_weight=100)]
    )
    node = NodeSchema(name="Note", namespace="Testing")

    NodeInheritanceHandler().inherit_containers(node=node, interfaces=[first, second])

    assert node.containers == [ContainerSchema(name="lacp", label="LACP", inherited=True)]


def test_inherited_containers_come_first_in_generic_order_followed_by_node_containers() -> None:
    first = _generic_with_containers(
        name="Item",
        containers=[ContainerSchema(name="layer2", label="Layer 2"), ContainerSchema(name="lacp", label="LACP")],
    )
    second = _generic_with_containers(
        name="Bundle",
        containers=[
            ContainerSchema(name="layer3", label="Layer 3"),
            ContainerSchema(name="lacp", label="Link aggregation"),
        ],
    )
    node = NodeSchema(
        name="Note",
        namespace="Testing",
        containers=[
            ContainerSchema(name="monitoring", label="Monitoring"),
            ContainerSchema(name="lacp", label="Bundle settings"),
            ContainerSchema(name="cabling", label="Cabling"),
        ],
    )

    NodeInheritanceHandler().inherit_containers(node=node, interfaces=[first, second])

    assert node.containers == [
        ContainerSchema(name="layer2", label="Layer 2", inherited=True),
        ContainerSchema(name="lacp", label="Bundle settings"),
        ContainerSchema(name="layer3", label="Layer 3", inherited=True),
        ContainerSchema(name="monitoring", label="Monitoring"),
        ContainerSchema(name="cabling", label="Cabling"),
    ]


def test_inherited_attribute_keeps_the_generic_container() -> None:
    generic = _generic_with_containers(name="Item", containers=[ContainerSchema(name="lacp", label="LACP")])
    node = NodeSchema(name="Note", namespace="Testing")

    NodeInheritanceHandler().inherit_from_interface(node=node, interface=generic)

    attribute = node.get_attribute(name="name")
    assert attribute.inherited is True
    assert attribute.container == "lacp"


def test_locally_redeclared_attribute_keeps_its_own_container() -> None:
    generic = _generic_with_containers(name="Item", containers=[ContainerSchema(name="lacp", label="LACP")])
    node = NodeSchema(
        name="Note",
        namespace="Testing",
        containers=[ContainerSchema(name="layer2", label="Layer 2")],
        attributes=[AttributeSchema(name="name", kind="Text", container="layer2")],
    )

    NodeInheritanceHandler().inherit_from_interface(node=node, interface=generic)

    assert [attribute.name for attribute in node.attributes] == ["name"]
    attribute = node.get_attribute(name="name")
    assert attribute.inherited is False
    assert attribute.container == "layer2"


def test_inheriting_twice_yields_the_same_containers() -> None:
    generic = _generic_with_containers(
        name="Item",
        containers=[ContainerSchema(name="lacp", label="LACP"), ContainerSchema(name="layer2", label="Layer 2")],
    )
    node = NodeSchema(name="Note", namespace="Testing")
    handler = NodeInheritanceHandler()

    handler.inherit_containers(node=node, interfaces=[generic])
    first_pass = [container.duplicate() for container in node.containers]
    handler.inherit_containers(node=node, interfaces=[generic])

    assert node.containers == first_pass
    assert [container.name for container in node.containers] == ["lacp", "layer2"]
