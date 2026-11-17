from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, NonNull

from infrahub.core.schema_change.constants import (
    SCHEMA_CHANGE_HISTORY_DEFAULT_LIMIT,
    SCHEMA_CHANGE_HISTORY_MAX_LIMIT,
    SchemaChangeStatus,
)
from infrahub.core.schema_change.history_reader import SchemaChangeHistoryReader
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
        ValidationError: When the limit or the offset is out of range.

    """
    page = validate_page_arguments(
        limit=limit,
        offset=offset,
        default_limit=SCHEMA_CHANGE_HISTORY_DEFAULT_LIMIT,
        max_limit=SCHEMA_CHANGE_HISTORY_MAX_LIMIT,
    )
    statuses = [SchemaChangeStatus(value) for value in status] if status is not None else None
    graphql_context: GraphqlContext = info.context
    branch_name = graphql_context.branch.name
    fields = extract_graphql_fields(info)

    result: dict[str, Any] = {}
    async with graphql_context.db.start_session(read_only=True) as db:
        reader = SchemaChangeHistoryReader(db=db)
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
        NonNull(SchemaChangeStatusType), description="Return only the schema changes with one of these statuses."
    ),
    description=(
        "Retrieve the schema changes of the branch of the request: the applied ones by version, "
        "then the others by the time they were created."
    ),
    resolver=infrahub_schema_change_resolver,
    required=True,
)
