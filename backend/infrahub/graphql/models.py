from pydantic import BaseModel


# Corresponds to infrahub.graphql.manager.OrderInput
class OrderModel(BaseModel):
    disable: bool | None = None
