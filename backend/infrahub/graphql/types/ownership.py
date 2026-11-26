from __future__ import annotations

from graphene import Boolean, Enum, Field, InputObjectType, List, NonNull, ObjectType, String

from infrahub.core.ownership.models import OwnerOrigin, OwnerState
from infrahub.graphql.resolvers.ownership import metadata_node_resolver

OwnerStateEnum = Enum.from_enum(OwnerState, name="OwnerState")
OwnerOriginEnum = Enum.from_enum(OwnerOrigin, name="OwnerOrigin")


class InfrahubMetadataNode(ObjectType):
    """A node that metadata refers to: an owner, a source, or the origin of owners."""

    id = String(required=True)
    kind = String(required=False, resolver=metadata_node_resolver)
    display_label = String(required=False, resolver=metadata_node_resolver)
    hfid = List(NonNull(String), required=False, resolver=metadata_node_resolver)
    is_deleted = Boolean(required=True, resolver=metadata_node_resolver)


class InfrahubOwnership(ObjectType):
    """Owner state of a node or a field, and the owners that apply to it."""

    state = Field(
        OwnerStateEnum,
        required=True,
        description="What a user set on the item itself. A copy from an object template is INHERIT",
    )
    origin = Field(
        OwnerOriginEnum, required=False, description="Where the owners that apply come from. Null when nothing applies"
    )
    origin_node = Field(
        InfrahubMetadataNode, required=False, description="The profile, template, parent or node that holds the owners"
    )
    owners = List(
        NonNull(InfrahubMetadataNode),
        required=True,
        description="Owners that apply, own or inherited. A deleted owner has is_deleted: true",
    )


class InfrahubFieldOwnership(ObjectType):
    field = String(required=True)
    ownership = Field(InfrahubOwnership, required=True)


OWNERS_INPUT_DESCRIPTION = "Left out: no change. null: inherit. []: no owner. List: own owners"


class MetadataNodeInput(InputObjectType):
    """An owner or a source. Give `id`, `hfid` with `kind`, or `name`."""

    id = String(required=False)
    hfid = List(NonNull(String), required=False)
    kind = String(required=False)
    name = String(
        required=False,
        description="The HFID of a kind that has one HFID value. Without `kind`: the name of an account group",
    )


class FieldOwnersInput(InputObjectType):
    field = String(required=True, description="Name of an attribute or a relationship")
    owners = List(NonNull(MetadataNodeInput), description="null: inherit. []: no owner. List: own owners")


class NodeMetadataInput(InputObjectType):
    owners = List(NonNull(MetadataNodeInput), description=OWNERS_INPUT_DESCRIPTION)
    field_owners = List(NonNull(FieldOwnersInput), description="The owners of attributes and relationships, by name")
    target_owners = List(
        NonNull(MetadataNodeInput),
        description="Profiles and object templates only: the owners given to their nodes. null: gives nothing",
    )
    target_field_owners = List(
        NonNull(FieldOwnersInput),
        description="Profiles and object templates only: the owners given to one field of their nodes",
    )
    sources = List(NonNull(MetadataNodeInput), description="Left out: no change. null or []: no sources")
