from __future__ import annotations

from typing import Any

from graphene import DateTime, Field, ObjectType, String
from graphene.types.objecttype import ObjectTypeOptions

from infrahub.core.schema import MainSchemaTypes


class InfrahubObjectOptions(ObjectTypeOptions):
    schema: MainSchemaTypes


class InfrahubNodeMetaObject(ObjectType):
    created_at = DateTime(required=False, description="Date/Time the object has been created")
    created_by = String(
        required=False, description="UUID of the user that created the object, even if the user is later deleted"
    )
    updated_by = String(
        required=False, description="UUID of the user that last modified the object, even if the user is later deleted"
    )
    updated_at = DateTime(
        required=False, description="Date/Time when the object was last modified by a user or a system task"
    )


class InfrahubNodeMeta(ObjectType):
    node_metadata = Field(InfrahubNodeMetaObject, required=False)


class InfrahubObject(InfrahubNodeMeta):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: MainSchemaTypes | None = None,
        interfaces: tuple = (),
        _meta: InfrahubObjectOptions | None = None,
        **options: Any,
    ) -> None:
        if not isinstance(schema, MainSchemaTypes):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubObjectOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, interfaces=interfaces, **options)


class InfrahubObjectWithoutMeta(ObjectType):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: MainSchemaTypes | None = None,
        interfaces: tuple = (),
        _meta: InfrahubObjectOptions | None = None,
        **options: Any,
    ) -> None:
        if not isinstance(schema, MainSchemaTypes):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubObjectOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, interfaces=interfaces, **options)
