from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, NonNull

from infrahub.core.schema_change.constants import SCHEMA_CHANGE_HISTORY_DEFAULT_LIMIT, SCHEMA_CHANGE_HISTORY_MAX_LIMIT
from infrahub.core.schema_change.enums import SchemaChangeStatus
from infrahub.core.schema_change.factory import build_schema_change_history_reader
from infrahub.exceptions import AuthorizationError
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.loaders.schema_change import SchemaChangeLoaders
from infrahub.graphql.resolvers.schema_change import build_schema_change_node, validate_page_arguments
from infrahub.graphql.types.schema_change import InfrahubSchemaChanges
from infrahub.graphql.types.schema_change import SchemaChangeStatus as SchemaChangeStatusType

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


async def infrahub_schema_change_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    limit: int | None = None,
    offset: int | None = None,
    status: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve one page of the schema changes of the branch of the request.

    Raises:
        AuthorizationError: When the request has no authenticated account.
        ValidationError: When the limit or the offset is out of range.

    """
    graphql_context: GraphqlContext = info.context
    # The checker pipeline finds this field by its name only when it is not inside a fragment.
    if graphql_context.account_session is None or not graphql_context.account_session.authenticated:
        raise AuthorizationError("Authentication is required to perform this operation")
    page = validate_page_arguments(
        limit=limit,
        offset=offset,
        default_limit=SCHEMA_CHANGE_HISTORY_DEFAULT_LIMIT,
        max_limit=SCHEMA_CHANGE_HISTORY_MAX_LIMIT,
    )
    statuses = [SchemaChangeStatus(value) for value in status] if status is not None else None
    branch_name = graphql_context.branch.name
    fields = extract_graphql_fields(info)

    result: dict[str, Any] = {}
    async with graphql_context.db.start_session(read_only=True) as db:
        reader = build_schema_change_history_reader(db=db)
        if "edges" in fields:
            history_page = await reader.list_schema_changes(
                branch=branch_name, limit=page.limit, offset=page.offset, statuses=statuses
            )
            loaders = SchemaChangeLoaders(open_session=graphql_context.db.start_session)
            result["edges"] = [
                {"node": build_schema_change_node(entry=entry, loaders=loaders)} for entry in history_page.entries
            ]
            result["count"] = history_page.count
        elif "count" in fields:
            result["count"] = await reader.count_schema_changes(branch=branch_name, statuses=statuses)

    return result


InfrahubSchemaChange = Field(
    InfrahubSchemaChanges,
    limit=Int(
        description=(
            f"Number of schema changes to return. Default {SCHEMA_CHANGE_HISTORY_DEFAULT_LIMIT}, "
            f"maximum {SCHEMA_CHANGE_HISTORY_MAX_LIMIT}, minimum 1."
        )
    ),
    offset=Int(description="Number of schema changes to skip. Minimum 0."),
    status=List(
        NonNull(SchemaChangeStatusType),
        description=(
            "Return only the schema changes with one of these statuses. An empty list returns no schema change."
        ),
    ),
    description="Retrieve the schema changes of the branch of the request, the most recently created first.",
    resolver=infrahub_schema_change_resolver,
    required=True,
)
