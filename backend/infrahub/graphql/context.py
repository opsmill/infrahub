from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.exceptions import NodeNotFoundError, ValidationError

if TYPE_CHECKING:
    from .initialization import GraphqlContext
    from .types.context import ContextInput


async def apply_external_context(graphql_context: GraphqlContext, context_input: ContextInput | None) -> None:
    """Applies context provided by an external mutation to the GraphQL context"""
    if not context_input or not context_input.account:
        return

    try:
        account = await NodeManager.get_one_by_id_or_default_filter(
            db=graphql_context.db, id=str(context_input.account.id), kind=InfrahubKind.GENERICACCOUNT
        )
    except NodeNotFoundError as exc:
        raise ValidationError(input_value="Unable to set context for account that doesn't exist") from exc

    graphql_context.active_account_session.account_id = account.id
