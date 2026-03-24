"""Resolvers for account metadata fields (created_by, updated_by)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.loaders.account import AccountDataLoader, AccountLoaderParams

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch.models import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext


class AccountMetadataResolver:
    """Resolver class for account metadata fields (created_by, updated_by).

    This class maintains DataLoader instances to enable batching and caching
    of account lookups across multiple fields within the same request.
    """

    def __init__(self) -> None:
        self._data_loader_instances: dict[AccountLoaderParams, AccountDataLoader] = {}

    def _get_or_create_loader(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp | None,
        fields: dict[str, Any],
    ) -> AccountDataLoader:
        """Get an existing loader or create a new one for the given parameters."""
        params = AccountLoaderParams(branch=branch, at=at, fields=fields)

        if params not in self._data_loader_instances:
            self._data_loader_instances[params] = AccountDataLoader(db=db, params=params)

        return self._data_loader_instances[params]

    async def resolve(
        self,
        parent: dict[str, Any],
        info: GraphQLResolveInfo,
    ) -> dict[str, Any] | None:
        """Resolve created_by/updated_by fields in metadata objects.

        The parent dict should contain {"id": "account-uuid", "__kind__": "CoreAccount"}
        for the field being resolved, or the field value may be None.
        """
        field_name = info.field_name  # "created_by" or "updated_by"
        account_data = parent.get(field_name)

        if not account_data or not account_data.get("id"):
            return None

        account_id = account_data["id"]
        graphql_context: GraphqlContext = info.context

        # Extract the fields requested for this account
        fields = extract_graphql_fields(info=info)

        # Get or create a loader for these parameters
        loader = self._get_or_create_loader(
            db=graphql_context.db,
            branch=graphql_context.branch,
            at=graphql_context.at,
            fields=fields,
        )

        return await loader.load(account_id)


async def account_metadata_resolver(
    parent: dict[str, Any],
    info: GraphQLResolveInfo,
) -> dict[str, Any] | None:
    """Function resolver that delegates to the AccountMetadataResolver on the context."""
    graphql_context: GraphqlContext = info.context
    resolver = graphql_context.account_metadata_resolver
    return await resolver.resolve(parent=parent, info=info)
