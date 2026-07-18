from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema


def _build_node_schema() -> NodeSchema:
    return NodeSchema(
        name="Widget",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="description", kind="Text", optional=True),
        ],
        relationships=[
            RelationshipSchema(name="owner", peer="TestingPerson", optional=True),
        ],
    )


class TestDiffIdlessElements:
    """Test elements without ids

    elements that are never persisted, e.g. generated relationships, must be
    matched by name and compared by value, exactly like elements with ids.
    """

    def test_identical_idless_elements_produce_no_diff(self) -> None:
        node = _build_node_schema()
        other = node.duplicate()

        diff = node.diff(other=other)

        assert not diff.has_diff

    def test_changed_idless_elements_are_reported_as_changed(self) -> None:
        node = _build_node_schema()
        other = node.duplicate()
        other.get_attribute(name="description").optional = False

        diff = node.diff(other=other)

        attrs_diff = diff.changed["attributes"]
        assert attrs_diff is not None
        assert set(attrs_diff.changed) == {"description"}

    def test_element_only_in_code_is_reported_one_sided(self) -> None:
        node = _build_node_schema()
        other = node.duplicate()
        node.attributes = [attr for attr in node.attributes if attr.name != "description"]

        diff = other.diff(other=node)

        attrs_diff = diff.changed["attributes"]
        assert attrs_diff is not None
        assert set(attrs_diff.added) == {"description"}


class TestUpdateOptionalTextFields:
    def test_empty_string_clears_existing_value(self) -> None:
        node = _build_node_schema()
        node.description = "a real description"
        other = node.duplicate()
        other.description = ""

        node.update(other=other)

        assert node.description is None

    def test_empty_string_on_both_sides_is_left_alone(self) -> None:
        node = _build_node_schema()
        node.description = ""
        other = node.duplicate()

        node.update(other=other)

        assert node.description == ""  # noqa: PLC1901

    def test_empty_string_with_local_none_is_left_alone(self) -> None:
        node = _build_node_schema()
        node.description = None
        other = node.duplicate()
        other.description = ""

        node.update(other=other)

        assert node.description is None
