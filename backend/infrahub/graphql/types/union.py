from __future__ import annotations

from graphene import Union
from graphene.types.union import UnionOptions

from infrahub.core import registry
from infrahub.core.schema import GroupSchema


class InfrahubUnionOptions(UnionOptions):
    schema = None


class InfrahubUnion(Union):
    class Meta:
        """We must provide a placeholder types because __init_subclass__ is defined at the parent level
        and it will automatically check if there is at least one type defined when the class is loaded."""

        types = ("PlaceHolder",)

    @classmethod
    def __init_subclass_with_meta__(cls, schema: GroupSchema = None, types=(), _meta=None, **options):  # pylint: disable=arguments-renamed
        if not isinstance(schema, GroupSchema):
            raise ValueError(f"You need to pass a valid GroupSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubUnionOptions(cls)

        _meta.schema = schema
        _meta.types = types

        super(Union, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    def resolve_type(cls, instance, info):
        branch = info.context["infrahub_branch"]

        if "type" in instance:
            return registry.get_graphql_type(name=f"Related{instance['type']}", branch=branch)

        raise ValueError("Unable to identify the type of the instance.")
