import ast
from typing import TYPE_CHECKING, Any, Self

from graphene import Boolean, InputObjectType, JSONString, Mutation, String
from graphql import GraphQLResolveInfo
from infrahub_sdk.utils import extract_fields
from pydantic import BaseModel

from infrahub.core import registry
from infrahub.core.attribute import BaseAttribute
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.convert_object_kind.schema_mapping import raise_if_unidirectional_relationships
from infrahub.core.relationship import RelationshipManager
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.graphql.mutations.mutation_create import create_node

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext


class InputDataForDestField(BaseModel):  # Only one of these fields can be not None
    attribute_value: Any | None = None
    peer_id: str | None = None
    peers_ids: list[str] | None = None


class InputForDestField(BaseModel):  # Only one of these fields can be not None
    source_field: str | None = None
    data: InputDataForDestField | None = None


def validate_node_relationships(node: Node) -> None:
    for name in node._relationships:
        relm: RelationshipManager = getattr(node, name)
        relm.validate()


async def get_all_peers_ids(node: Node, db: InfrahubDatabase) -> list[str]:
    all_peers: list[Node] = []
    for name in node._relationships:
        relm: RelationshipManager = getattr(node, name)
        peers = await relm.get_peers(db=db)
        all_peers.extend(peers.values())
    return [peer.id for peer in all_peers]


async def convert_object_type(
    node: Node, target_kind: str, mapping: dict[str, InputForDestField], branch: Branch, db: InfrahubDatabase
) -> Node:
    """Delete the node and return the new created one. If creation fails, the node is not deleted, and raise an error."""

    node_schema = node.get_schema()
    if not isinstance(node_schema, NodeSchema):
        raise ValueError(f"Only a node with a NodeSchema can be converted, got {type(node_schema)}")

    raise_if_unidirectional_relationships(node_schema)

    async with db.start_transaction() as dbt:  # noqa: PLR1702
        data = {}
        for dest_field_name, input_for_dest_field in mapping.items():
            if input_for_dest_field.source_field is not None:
                item = getattr(node, input_for_dest_field.source_field)
                if isinstance(item, BaseAttribute):
                    data[dest_field_name] = item.value
                elif isinstance(item, RelationshipManager):
                    if item.schema.cardinality == RelationshipCardinality.ONE:
                        peer = await item.get_peer(db=dbt)
                        if peer is None:
                            raise ValueError(f"Unable to find peer of {item=}")
                        data[dest_field_name] = {"id": peer.id}
                    elif item.schema.cardinality == RelationshipCardinality.MANY:
                        data[dest_field_name] = [{"id": peer.id} for _, peer in (await item.get_peers(db=dbt)).items()]
                    else:
                        raise ValueError(f"Unknown cardinality {item.schema.cardinality=}")
            else:
                assert input_for_dest_field.data is not None, f"{input_for_dest_field=}"
                if input_for_dest_field.data.attribute_value is not None:
                    data[dest_field_name] = input_for_dest_field.data.attribute_value
                elif input_for_dest_field.data.peer_id is not None:
                    data[dest_field_name] = input_for_dest_field.data.peer_id
                elif input_for_dest_field.data.peers_ids is not None:
                    data[dest_field_name] = input_for_dest_field.data.peers_ids
                else:
                    raise ValueError(f"No filled value for destination field {dest_field_name=}")

        deleted_node_peer_ids = await get_all_peers_ids(node=node, db=dbt)
        deleted_nodes = await NodeManager.delete(db=dbt, branch=branch, nodes=[node], cascade_delete=False)
        if len(deleted_nodes) != 1:
            raise ValueError(f"Deleted {len(deleted_nodes)} nodes instead of 1")

        target_schema = registry.get_node_schema(name=target_kind, branch=branch)
        node_created = await create_node(
            data=data,
            db=dbt,
            branch=branch,
            schema=target_schema,
            use_session_for_constraint_checks=False,
        )

        # Make sure relationships with constraints are not broken by retrieving them
        for peer_id in deleted_node_peer_ids:
            peer = await NodeManager.get_one(id=peer_id, db=dbt, prefetch_relationships=True, raise_on_error=True)
            # TODO don't assert here but it actually can't be None as raise_on_error is True, should overload
            assert peer is not None
            validate_node_relationships(node=peer)

        return node_created


class ConvertObjectTypeInput(InputObjectType):
    node_id = String(required=True)
    target_kind = String(required=True)
    fields_mapping = JSONString(required=True)  # keys are destination attributes/relationships names.
    branch = String(required=True)


class ConvertObjectType(Mutation):
    class Arguments:
        data = ConvertObjectTypeInput(required=True)

    ok = Boolean()
    # TODO Return created node as json?

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: ConvertObjectTypeInput,
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        # Not sure why json.loads doesn't work here, it seems double quotes become single quotes when deserializing server side
        mapping = ast.literal_eval(str(data.fields_mapping))

        fields_mapping: dict[str, InputForDestField] = {}
        for field, input_for_dest_field_str in mapping.items():
            fields_mapping[field] = InputForDestField(**input_for_dest_field_str)

        node_to_convert = await NodeManager.get_one(
            id=str(data.node_id), db=graphql_context.db, branch=str(data.branch)
        )
        new_node = await convert_object_type(
            node=node_to_convert,
            target_kind=str(data.target_kind),
            mapping=fields_mapping,
            branch=graphql_context.branch,
            db=graphql_context.db,
        )

        fields = await extract_fields(info.field_nodes[0].selection_set)
        result: dict[str, Any] = {"ok": True}
        if "object" in fields:
            result["object"] = await new_node.to_graphql(db=graphql_context.db, fields=fields.get("object", {}))
        return cls(**result)
