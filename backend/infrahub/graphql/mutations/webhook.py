from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self, cast

from graphene import InputObjectType, Mutation

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreWebhook
from infrahub.core.schema import NodeSchema
from infrahub.database import retry_db_transaction
from infrahub.events.utils import get_all_infrahub_node_kind_events
from infrahub.exceptions import ValidationError
from infrahub.log import get_logger

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext

log = get_logger()


@dataclass
class StringValue:
    value: str


@dataclass
class WebhookCreate:
    event_type: StringValue | None = field(default=None)
    node_kind: StringValue | None = field(default=None)


class WebhookUpdate(WebhookCreate):
    id: str | None = field(default=None)
    hfid: list[str] | None = field(default=None)


class InfrahubWebhookMutation(InfrahubMutationMixin, Mutation):
    _meta: InfrahubMutationOptions

    @classmethod
    def __init_subclass_with_meta__(
        cls, schema: NodeSchema | None = None, _meta: InfrahubMutationOptions | None = None, **options: dict[str, Any]
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context

        input_data = cast("WebhookCreate", data)

        _validate_input(graphql_context=graphql_context, branch=branch, input_data=input_data)

        obj, result = await super().mutate_create(info=info, data=data, branch=branch, database=database)

        return obj, result

    @classmethod
    @retry_db_transaction(name="object_update")
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
        node: Node | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context

        db = database or graphql_context.db

        input_data = cast("WebhookUpdate", data)

        _validate_input(graphql_context=graphql_context, branch=branch, input_data=input_data)

        obj = node or await NodeManager.find_object(
            db=db,
            kind=cls._meta.active_schema.kind,
            id=input_data.id,
            hfid=input_data.hfid,
            branch=branch,
        )

        webhook = cast(CoreWebhook, obj)

        event_type = input_data.event_type.value if input_data.event_type else webhook.event_type.value.value
        node_kind = input_data.node_kind.value if input_data.node_kind else webhook.node_kind.value

        if event_type and node_kind:
            updated_data = WebhookUpdate(
                event_type=StringValue(value=event_type), node_kind=StringValue(value=node_kind)
            )
            _validate_input(graphql_context=graphql_context, branch=branch, input_data=updated_data)

        try:
            obj, result = await cls._call_mutate_update(info=info, data=data, db=db, branch=branch, obj=obj)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        return obj, result


def _validate_input(graphql_context: GraphqlContext, branch: Branch, input_data: WebhookCreate) -> None:
    if input_data.node_kind:
        # Validate that the requested node_kind exists, will raise an error if not
        graphql_context.db.schema.get(name=input_data.node_kind.value, branch=branch, duplicate=False)

        if input_data.event_type:
            # If the event type is not set then all events are applicable, this will mean that some events
            # would be filtered out, as they won't match the node.
            if input_data.event_type.value not in get_all_infrahub_node_kind_events():
                raise ValidationError(
                    input_value=f"Defining a node_kind is not valid for {input_data.event_type.value} events"
                )
