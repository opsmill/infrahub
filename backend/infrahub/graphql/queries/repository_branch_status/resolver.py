from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.filters import BranchListFilters
from infrahub.core.branch.models import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.standard import StandardNodeOrdering, StandardNodeQueryFields
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.queries.branch import standard_node_ordering_from_order_input

from .kind_dispatch import policy_for_kind
from .paging import RepositoryBranchStatusRow, apply_value_filters, order_rows, page_rows
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

_BRANCH_FIELD_NAMES = frozenset({"name", "status", "is_default", "sync_with_git", "branched_from"})
_COMMIT_ATTRIBUTE_NAME = "commit"
_AT_QUERY_PARAMETER = "at"
_AT_REJECTION_MESSAGE = "at is not supported on InfrahubRepositoryBranchStatus: the branch row set is always current"


def _reject_historical_read(context: GraphqlContext) -> None:
    """Reject a request that asks for a past point in time.

    The rows come from the branch list, which is only ever the current one, so historical values
    would be paired with branches that did not exist then and would omit branches deleted since.
    The context resolves an absent `at` to the current time, so the request is the only place that
    still records whether the caller asked for one.

    Args:
        context: GraphQL request context.

    Raises:
        ValidationError: If the request carries an `at` parameter.

    """
    request = context.request
    if request is not None and request.query_params.get(_AT_QUERY_PARAMETER) is not None:
        raise ValidationError(_AT_REJECTION_MESSAGE)


class RepositoryBranchStatusResolver:
    """Resolve one repository's status as every branch in scope sees it, one row per branch."""

    def __init__(self, build_source: Callable[[InfrahubDatabase], RepositoryBranchAttributesSource]) -> None:
        self.build_source = build_source

    async def __call__(
        self,
        root: dict,  # noqa: ARG002
        info: GraphQLResolveInfo,
        id: str,
        limit: int | None = 40,
        offset: int | None = 0,
        name__value: str | None = None,
        partial_match: bool = False,
        status__value: str | None = None,
        order: MetadataOrderInput | None = None,
        sync_status__value: str | None = None,
        internal_status__value: str | None = None,
        own_values_only: bool = False,
    ) -> dict[str, Any]:
        """Resolve the repository's per-branch status rows.

        Args:
            root: Parent value, unused for a root field.
            info: GraphQL resolution info, carrying the request context and the field selection.
            id: UUID or name of the repository.
            limit: Page size. An explicit null is rejected rather than falling back to the default.
            offset: Number of rows to skip. An explicit null is rejected rather than falling back to
                the default.
            name__value: Branch name filter.
            partial_match: Match `name__value` as a substring rather than exactly.
            status__value: Branch status filter.
            order: Ordering over branch node metadata; the default order applies when it expresses
                no ordering.
            sync_status__value: Keep only rows whose resolved `sync_status` equals this value.
            internal_status__value: Keep only rows whose resolved `internal_status` equals this
                value.
            own_values_only: Keep only rows whose branch holds its own `commit` value rather than
                inheriting one, independent of the selected fields.

        Returns:
            The payload the GraphQL types consume: `edges`, and `count` when it was selected.

        Raises:
            ValidationError: If `limit` is null or below 1, if `offset` is null or negative, if the
                request asks for a past point in time, if `order` is contradictory, or if the
                repository's kind is not supported.
            NodeNotFoundError: If `id` resolves to no repository.
            PermissionDeniedError: If the caller may not view the repository's kind across both the
                default branch and other branches.

        """
        graphql_context: GraphqlContext = info.context

        # A nullable Int argument with a default still reaches here as None for an explicit null.
        if limit is None or limit < 1:
            raise ValidationError("limit must be >= 1")
        if offset is None or offset < 0:
            raise ValidationError("offset must be >= 0")
        _reject_historical_read(context=graphql_context)

        node_ordering = standard_node_ordering_from_order_input(order)

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
        # The id path of the lookup does not enforce `kind`, so a node of any kind resolves here.
        repository_kinds = db.schema.get_generic_schema(
            name=InfrahubKind.GENERICREPOSITORY, branch=None, duplicate=False
        ).used_by
        if repository.get_kind() not in repository_kinds:
            raise NodeNotFoundError(
                branch_name=registry.default_branch,
                node_type=InfrahubKind.GENERICREPOSITORY,
                identifier=id,
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
        edge_fields = fields.get("edges") or {}
        node_fields = edge_fields.get("node") or {}
        node_metadata_fields = edge_fields.get("node_metadata") or {}
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
        rows = apply_value_filters(
            rows=rows,
            sync_status=sync_status__value,
            internal_status=internal_status__value,
            own_values_only=own_values_only,
        )
        # An `order` argument can be present yet express no ordering, e.g. an empty input object.
        if node_ordering == StandardNodeOrdering():
            rows = order_rows(rows=rows)

        result: dict[str, Any] = {}
        if "count" in fields:
            result["count"] = len(rows)

        attribute_schemas = self._attribute_schemas(db=db, policy=policy)
        result["edges"] = [
            await self._build_edge(
                row=row,
                attribute_schemas=attribute_schemas,
                node_fields=node_fields,
                node_metadata_fields=node_metadata_fields,
            )
            for row in page_rows(rows=rows, offset=offset, limit=limit)
        ]
        return result

    def _attribute_names(
        self, node_fields: dict[str, Any], policy: RepositoryKindPolicy, own_values_only: bool
    ) -> set[str]:
        selected = set(policy.attribute_names & node_fields.keys())
        # The own-values filter reads `commit` whether or not the caller selected it.
        if own_values_only:
            selected.add(_COMMIT_ATTRIBUTE_NAME)
        return selected

    def _attribute_schemas(self, db: InfrahubDatabase, policy: RepositoryKindPolicy) -> dict[str, AttributeSchema]:
        schema = db.schema.get(name=policy.kind, branch=None, duplicate=False)
        return {name: schema.get_attribute(name=name) for name in sorted(policy.attribute_names)}

    async def _build_edge(
        self,
        row: RepositoryBranchStatusRow,
        attribute_schemas: dict[str, AttributeSchema],
        node_fields: dict[str, Any],
        node_metadata_fields: dict[str, Any],
    ) -> dict[str, Any]:
        # The branch half goes through the branch model's own serialisation, so the value-field
        # wrapping and the metadata shape cannot drift from the branch query's.
        branch_fields = {name: node_fields[name] for name in _BRANCH_FIELD_NAMES & node_fields.keys()}
        edge = await row.branch.to_graphql(
            fields=StandardNodeQueryFields(node=branch_fields, node_metadata=node_metadata_fields)
        )

        node = edge["node"]
        for attribute_name, attribute_schema in attribute_schemas.items():
            node[attribute_name] = build_attribute_payload(
                value=row.values.get(attribute_name), attribute_schema=attribute_schema
            )
        return edge
