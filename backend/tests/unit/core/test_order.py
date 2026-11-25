import pytest

from infrahub.constants.enums import OrderDirection
from infrahub.core.order import AttributeValuePriority, NodeMetaOrder, OrderByEntry, OrderModel
from infrahub.exceptions import ValidationError


@pytest.mark.parametrize(
    "order",
    [
        pytest.param(OrderModel(disable=True), id="disabled"),
        pytest.param(OrderModel(node_metadata=NodeMetaOrder(created_at=OrderDirection.ASC)), id="metadata"),
        pytest.param(OrderModel(by=(OrderByEntry(field="name__value"),)), id="attribute"),
    ],
)
def test_attribute_value_priority_cannot_be_combined_with_another_order(order: OrderModel) -> None:
    with pytest.raises(ValidationError, match="Cannot combine attribute value priority with another order"):
        OrderModel.model_validate(
            order.model_dump() | {"priority": AttributeValuePriority(attribute="conclusion", value="failure")}
        )
