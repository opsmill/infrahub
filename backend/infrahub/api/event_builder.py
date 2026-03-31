from fastapi import Request

from infrahub.auth import AccountSession, AuthResult
from infrahub.context import InfrahubContext
from infrahub.core.branch.models import Branch
from infrahub.events.account_action import AccountLoggedInEvent, AccountLoggedOutEvent, AuthMethod, SSOProvider
from infrahub.events.models import EventMeta


async def make_event_meta(account_session: AccountSession, branch: Branch) -> EventMeta:
    return EventMeta(
        branch=branch,
        context=InfrahubContext.init(branch=branch, account=account_session),
        account_id=account_session.account_id,
    )


def make_login_event(
    auth_result: AuthResult,
    request: Request,
    auth_method: AuthMethod,
    event_meta: EventMeta,
    sso_provider: SSOProvider | None = None,
) -> AccountLoggedInEvent:
    return AccountLoggedInEvent(
        meta=event_meta,
        kind=auth_result.kind,
        account_id=auth_result.account_id,
        account_name=auth_result.account_name,
        account_type=auth_result.account_type,
        sso_provider=sso_provider,
        auth_method=auth_method,
        session_id=str(auth_result.session_id),
        groups=auth_result.groups,
        roles=auth_result.roles,
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


def make_logout_event(
    account_id: str, request: Request, account_name: str, session_id: str, kind: str, event_meta: EventMeta
) -> AccountLoggedOutEvent:
    return AccountLoggedOutEvent(
        meta=event_meta,
        kind=kind,
        account_id=account_id,
        account_name=account_name,
        session_id=session_id,
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
