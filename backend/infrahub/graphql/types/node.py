from __future__ import annotations

from typing import Optional, Union

from graphene import ObjectType
from graphene.types.objecttype import ObjectTypeOptions

from infrahub.core.schema import GenericSchema, NodeSchema, ProfileSchema

from .mixin import GetListMixin


class InfrahubObjectOptions(ObjectTypeOptions):
    schema = None


class InfrahubObject(ObjectType, GetListMixin):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: Optional[Union[NodeSchema, GenericSchema, ProfileSchema]] = None,
        interfaces=(),
        _meta=None,
        **options,
    ):  # pylint: disable=arguments-differ
        if not isinstance(schema, (NodeSchema, GenericSchema, ProfileSchema)):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubObjectOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, interfaces=interfaces, **options)
