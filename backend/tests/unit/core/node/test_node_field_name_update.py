from uuid import uuid4

import pytest

from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.basenode_schema import BaseNodeSchema


class TestNodeUpdate:
    @pytest.fixture
    def original_node_schema(self) -> BaseNodeSchema:
        return BaseNodeSchema(
            namespace="Shnamespace",
            name="Shname",
        )

    @pytest.fixture
    def new_node_schema(self) -> BaseNodeSchema:
        return BaseNodeSchema(
            namespace="Shnamespace",
            name="Shname",
        )

    def test_no_fields_update(self, original_node_schema: BaseNodeSchema, new_node_schema: BaseNodeSchema):
        original_node_schema.update(other=new_node_schema)

        assert original_node_schema.uniqueness_constraints is None
        assert original_node_schema.human_friendly_id is None
        assert original_node_schema.display_labels is None
        assert original_node_schema.order_by is None

    def test_new_fields_update(self, original_node_schema: BaseNodeSchema, new_node_schema: BaseNodeSchema):
        new_node_schema.uniqueness_constraints = [["abc__value"]]
        new_node_schema.human_friendly_id = ["abc__value"]
        new_node_schema.display_labels = ["abc__value"]
        new_node_schema.order_by = ["abc__value"]

        original_node_schema.update(other=new_node_schema)

        assert original_node_schema.uniqueness_constraints == new_node_schema.uniqueness_constraints
        assert original_node_schema.human_friendly_id == new_node_schema.human_friendly_id
        assert original_node_schema.display_labels == new_node_schema.display_labels
        assert original_node_schema.order_by == new_node_schema.order_by

    def test_old_fields_no_update(self, original_node_schema: BaseNodeSchema, new_node_schema: BaseNodeSchema):
        original_node_schema.attributes = [AttributeSchema(name="abc", kind="Text")]
        uniqueness_constraints = [["abc__value"]]
        human_friendly_id = ["abc__value"]
        display_labels = ["abc__value"]
        order_by = ["abc__value"]
        original_node_schema.uniqueness_constraints = uniqueness_constraints
        original_node_schema.human_friendly_id = human_friendly_id
        original_node_schema.display_labels = display_labels
        original_node_schema.order_by = order_by

        original_node_schema.update(other=new_node_schema)

        assert original_node_schema.uniqueness_constraints == uniqueness_constraints
        assert original_node_schema.human_friendly_id == human_friendly_id
        assert original_node_schema.display_labels == display_labels
        assert original_node_schema.order_by == order_by

    @pytest.mark.parametrize(
        ["uniqueness_constraints", "human_friendly_id", "display_labels", "order_by"],
        [(None, None, None, None), ([["def__value"]], ["def__value"], ["def__value"], ["def__value"])],
    )
    def test_old_fields_with_update(
        self,
        original_node_schema: BaseNodeSchema,
        new_node_schema: BaseNodeSchema,
        uniqueness_constraints,
        human_friendly_id,
        display_labels,
        order_by,
    ):
        original_node_schema.attributes = [AttributeSchema(name="abc", kind="Text")]
        original_node_schema.uniqueness_constraints = [["abc__value"]]
        original_node_schema.human_friendly_id = ["abc__value"]
        original_node_schema.display_labels = ["abc__value"]
        original_node_schema.order_by = ["abc__value"]
        original_uniqueness_constraints = original_node_schema.uniqueness_constraints
        original_human_friendly_id = original_node_schema.human_friendly_id
        original_display_labels = original_node_schema.display_labels
        original_order_by = original_node_schema.order_by
        new_node_schema.uniqueness_constraints = uniqueness_constraints
        new_node_schema.human_friendly_id = human_friendly_id
        new_node_schema.display_labels = display_labels
        new_node_schema.order_by = order_by

        original_node_schema.update(other=new_node_schema)

        assert original_node_schema.uniqueness_constraints == uniqueness_constraints or original_uniqueness_constraints
        assert original_node_schema.human_friendly_id == human_friendly_id or original_human_friendly_id
        assert original_node_schema.display_labels == display_labels or original_display_labels
        assert original_node_schema.order_by == order_by or original_order_by

    def test_old_fields_with_updated_name(
        self,
        original_node_schema: BaseNodeSchema,
        new_node_schema: BaseNodeSchema,
    ):
        attribute_id = str(uuid4())
        original_node_schema.attributes = [AttributeSchema(id=attribute_id, name="abc", kind="Text")]
        original_node_schema.uniqueness_constraints = [["abc__value"]]
        original_node_schema.human_friendly_id = ["abc__value"]
        original_node_schema.display_labels = ["abc__value"]
        original_node_schema.order_by = ["abc__value"]
        new_node_schema.attributes = [AttributeSchema(id=attribute_id, name="def", kind="Text")]
        new_node_schema.uniqueness_constraints = None
        new_node_schema.human_friendly_id = None
        new_node_schema.display_labels = None
        new_node_schema.order_by = None

        original_node_schema.update(other=new_node_schema)

        assert original_node_schema.uniqueness_constraints == [["def__value"]]
        assert original_node_schema.human_friendly_id == ["def__value"]
        assert original_node_schema.display_labels == ["def__value"]
        assert original_node_schema.order_by == ["def__value"]


# TODO: test updating rel
# TODO: test deleting attr
# TODO: test deleting rel
