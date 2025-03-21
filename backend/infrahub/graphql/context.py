from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import GlobalPermissions, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.permissions.globals import define_global_permission_from_branch

if TYPE_CHECKING:
    from .initialization import GraphqlContext
    from .types.context import ContextInput


async def apply_external_context(graphql_context: GraphqlContext, context_input: ContextInput | None) -> None:
    """Applies context provided by an external mutation to the GraphQL context"""
    if not context_input or not context_input.account:
        return

    if graphql_context.active_account_session.account_id == context_input.account.id:
        # If the account_id from the request context is the same as the current account
        # there's no point moving forward with other checks to override the current
        # context we can just continue with what is already there.
        return

    permission = define_global_permission_from_branch(
        permission=GlobalPermissions.OVERRIDE_CONTEXT, branch_name=graphql_context.branch.name
    )

    graphql_context.active_permissions.raise_for_permission(permission=permission)

    try:
        account = await NodeManager.get_one_by_id_or_default_filter(
            db=graphql_context.db, id=str(context_input.account.id), kind=InfrahubKind.GENERICACCOUNT
        )
    except NodeNotFoundError as exc:
        raise ValidationError(input_value="Unable to set context for account that doesn't exist") from exc

    graphql_context.active_account_session.account_id = account.id
