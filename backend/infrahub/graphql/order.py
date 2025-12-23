from __future__ import annotations

from typing import Any

from infrahub.core.order import OrderModel


def deserialize_order_input(input_data: dict[str, Any] | None) -> OrderModel | None:
    # Corresponds to infrahub.graphql.manager.OrderInput
    if not input_data:
        return None

    order_model = OrderModel(**input_data)
    order_model.validate()
    return order_model
