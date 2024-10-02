from __future__ import annotations

from typing import Any, Optional

from graphene import ObjectType
from graphene.types.objecttype import ObjectTypeOptions

from infrahub.core.schema import GenericSchema, MainSchemaTypes, NodeSchema, ProfileSchema


class InfrahubObjectOptions(ObjectTypeOptions):
    schema: MainSchemaTypes


class InfrahubObject(ObjectType):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls,
        schema: Optional[MainSchemaTypes] = None,
        interfaces: tuple = (),
        _meta: InfrahubObjectOptions | None = None,
        **options: Any,
    ) -> None:
        if not isinstance(schema, (NodeSchema, GenericSchema, ProfileSchema)):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubObjectOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, interfaces=interfaces, **options)
