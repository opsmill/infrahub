from typing import Any

from graphene import BigInt, Boolean, Field, InputObjectType, Int, String
from graphene.types.generic import GenericScalar

from infrahub.core import registry
from infrahub.graphql.types.attribute import GenericPoolInput


class BaseAttributeCreate(InputObjectType):
    is_visible = Boolean(required=False)
    is_protected = Boolean(required=False)
    source = String(required=False)
    owner = String(required=False)

    @classmethod
    def __init_subclass__(cls, **kwargs: dict[str, Any]) -> None:
        super().__init_subclass__(**kwargs)
        registry.input_type[cls.__name__] = cls


class BaseAttributeUpdate(InputObjectType):
    is_default = Boolean(required=False)
    is_visible = Boolean(required=False)
    is_protected = Boolean(required=False)
    source = String(required=False)
    owner = String(required=False)

    @classmethod
    def __init_subclass__(cls, **kwargs: dict[str, Any]) -> None:
        super().__init_subclass__(**kwargs)
        registry.input_type[cls.__name__] = cls


class TextAttributeCreate(BaseAttributeCreate):
    value = String(required=False)


class TextAttributeUpdate(BaseAttributeUpdate):
    value = String(required=False)


class StringAttributeCreate(BaseAttributeCreate):
    value = String(required=False)


class StringAttributeUpdate(BaseAttributeUpdate):
    value = String(required=False)


class NumberAttributeCreate(BaseAttributeCreate):
    value = BigInt(required=False)
    from_pool = Field(GenericPoolInput, required=False)


class NumberAttributeUpdate(BaseAttributeUpdate):
    value = BigInt(required=False)
    from_pool = Field(GenericPoolInput, required=False)


class IntAttributeCreate(BaseAttributeCreate):
    value = Int(required=False)


class IntAttributeUpdate(BaseAttributeUpdate):
    value = Int(required=False)


class CheckboxAttributeCreate(BaseAttributeCreate):
    value = Boolean(required=False)


class CheckboxAttributeUpdate(BaseAttributeUpdate):
    value = Boolean(required=False)


class BoolAttributeCreate(BaseAttributeCreate):
    value = Boolean(required=False)


class BoolAttributeUpdate(BaseAttributeUpdate):
    value = Boolean(required=False)


class ListAttributeCreate(BaseAttributeCreate):
    value = GenericScalar(required=False)


class ListAttributeUpdate(BaseAttributeUpdate):
    value = GenericScalar(required=False)


class JSONAttributeCreate(BaseAttributeCreate):
    value = GenericScalar(required=False)


class JSONAttributeUpdate(BaseAttributeUpdate):
    value = GenericScalar(required=False)


class AnyAttributeCreate(BaseAttributeCreate):
    value = GenericScalar(required=False)


class AnyAttributeUpdate(BaseAttributeUpdate):
    value = GenericScalar(required=False)
