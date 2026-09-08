from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.filters import BranchListFilters
from infrahub.core.branch.models import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.exceptions import ValidationError
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.queries.branch import standard_node_ordering_from_order_input

from .kind_dispatch import policy_for_kind
from .paging import RepositoryBranchStatusRow, order_rows, page_rows
from .payload import build_attribute_payload
from .permissions import RepositoryBranchStatusPermissionGuard

if TYPE_CHECKING:
    from collections.abc import Callable

    from graphql import GraphQLResolveInfo

    from infrahub.core.repository_branch_status.interface import RepositoryBranchAttributesSource
    from infrahub.core.schema.attribute_schema import AttributeSchema
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.graphql.types.metadata import MetadataOrderInput

    from .kind_dispatch import RepositoryKindPolicy


class RepositoryBranchStatusResolver:
    """Resolve one repository's status as every branch in scope sees it, one row per branch.

    The `sync_status__value`, `internal_status__value` and `own_values_only` arguments are accepted
    but do not narrow the rows or the count yet, because the attribute values are still
    placeholders. `own_values_only` does already widen the attributes read, so the read set is the
    same once the filters apply.
    """

    def __init__(self, build_source: Callable[[InfrahubDatabase], RepositoryBranchAttributesSource]) -> None:
        self.build_source = build_source

    async def __call__(
        self,
        root: dict,  # noqa: ARG002
        info: GraphQLResolveInfo,
        id: str,
        limit: int = 40,
        offset: int = 0,
        name__value: str | None = None,
        partial_match: bool = False,
        status__value: str | None = None,
        order: MetadataOrderInput | None = None,
        sync_status__value: str | None = None,  # noqa: ARG002
        internal_status__value: str | None = None,  # noqa: ARG002
        own_values_only: bool = False,
    ) -> dict[str, Any]:
        """Resolve the repository's per-branch status rows.

        Args:
            root: Parent value, unused for a root field.
            info: GraphQL resolution info, carrying the request context and the field selection.
            id: UUID or name of the repository.
            limit: Page size.
            offset: Number of rows to skip.
            name__value: Branch name filter.
            partial_match: Match `name__value` as a substring rather than exactly.
            status__value: Branch status filter.
            order: Ordering over branch node metadata; the default order applies when omitted.
            sync_status__value: Accepted, not applied yet.
            internal_status__value: Accepted, not applied yet.
            own_values_only: Accepted, not applied yet; widens the attributes read.

        Returns:
            The payload the GraphQL types consume: `edges`, and `count` when it was selected.

        Raises:
            ValidationError: If `limit` is below 1, if `offset` is negative, if `order` is
                contradictory, or if the repository's kind is not supported.
            NodeNotFoundError: If `id` resolves to no repository.
            PermissionDeniedError: If the caller may not view the repository's kind across both the
                default branch and other branches.

        """
        if limit < 1:
            raise ValidationError("limit must be >= 1")
        if offset < 0:
            raise ValidationError("offset must be >= 0")

        node_ordering = standard_node_ordering_from_order_input(order)

        graphql_context: GraphqlContext = info.context
        db = graphql_context.db

        guard = RepositoryBranchStatusPermissionGuard(context=graphql_context)
        guard.ensure_any_kind_viewable()

        repository = await NodeManager.get_one_by_id_or_default_filter(
            db=db,
            id=id,
            kind=InfrahubKind.GENERICREPOSITORY,
            branch=None,
            at=graphql_context.at,
        )
        policy = policy_for_kind(kind=repository.get_kind())
        guard.ensure_kind_viewable(policy=policy)

        branches = await Branch.get_list(
            db=db,
            limit=None,
            exclude_global=True,
            exclude_terminal=True,
            branch_filters=BranchListFilters(
                name=name__value,
                partial_match=partial_match,
                status=BranchStatus(status__value) if status__value else None,
                sync_with_git=policy.sync_with_git_filter,
            ),
            node_ordering=node_ordering,
        )

        fields = extract_graphql_fields(info)
        node_fields = (fields.get("edges") or {}).get("node") or {}
        attribute_names = self._attribute_names(node_fields=node_fields, policy=policy, own_values_only=own_values_only)

        attributes = await self.build_source(db).read(
            repository_ids=[repository.id],
            branch_names=[branch.name for branch in branches],
            attribute_names=attribute_names,
            at=graphql_context.at,
        )

        rows = [
            RepositoryBranchStatusRow(
                branch=branch,
                values=attributes.for_branch(repository_id=repository.id, branch_name=branch.name),
            )
            for branch in branches
        ]
        if order is None:
            rows = order_rows(rows=rows)

        result: dict[str, Any] = {}
        if "count" in fields:
            result["count"] = len(rows)

        attribute_schemas = self._attribute_schemas(db=db, policy=policy)
        result["edges"] = [
            {"node": self._build_node(row=row, attribute_schemas=attribute_schemas)}
            for row in page_rows(rows=rows, offset=offset, limit=limit)
        ]
        return result

    def _attribute_names(
        self, node_fields: dict[str, Any], policy: RepositoryKindPolicy, own_values_only: bool
    ) -> set[str]:
        attribute_names = set(policy.attribute_names & node_fields.keys())
        if own_values_only:
            attribute_names.add("commit")
        return attribute_names

    def _attribute_schemas(self, db: InfrahubDatabase, policy: RepositoryKindPolicy) -> dict[str, AttributeSchema]:
        schema = db.schema.get(name=policy.kind, branch=None, duplicate=False)
        return {name: schema.get_attribute(name=name) for name in sorted(policy.attribute_names)}

    def _build_node(
        self, row: RepositoryBranchStatusRow, attribute_schemas: dict[str, AttributeSchema]
    ) -> dict[str, Any]:
        node: dict[str, Any] = {
            "name": row.branch.name,
            "status": row.branch.status.value,
            "is_default": row.branch.is_default,
            "sync_with_git": row.branch.sync_with_git,
            "branched_from": row.branch.branched_from,
            "commit": None,
            "sync_status": None,
            "internal_status": None,
            "ref": None,
        }
        for attribute_name, attribute_schema in attribute_schemas.items():
            node[attribute_name] = build_attribute_payload(
                value=row.values.get(attribute_name), attribute_schema=attribute_schema
            )
        return node
