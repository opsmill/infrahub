from graphene import Boolean, InputObjectType, Int, String
from graphene.types.generic import GenericScalar

from infrahub.core import registry


class BaseAttributeInput(InputObjectType):
    is_visible = Boolean(required=False)
    is_protected = Boolean(required=False)
    source = String(required=False)
    owner = String(required=False)

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        registry.input_type[cls.__name__] = cls


class TextAttributeInput(BaseAttributeInput):
    value = String(required=False)


class StringAttributeInput(BaseAttributeInput):
    value = String(required=False)


class NumberAttributeInput(BaseAttributeInput):
    value = Int(required=False)


class IntAttributeInput(BaseAttributeInput):
    value = Int(required=False)


class CheckboxAttributeInput(BaseAttributeInput):
    value = Boolean(required=False)


class BoolAttributeInput(BaseAttributeInput):
    value = Boolean(required=False)


class ListAttributeInput(BaseAttributeInput):
    value = GenericScalar(required=False)


class AnyAttributeInput(BaseAttributeInput):
    value = GenericScalar(required=False)
