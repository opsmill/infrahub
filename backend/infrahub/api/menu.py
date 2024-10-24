from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from infrahub.api.dependencies import get_branch_dep, get_current_user, get_db
from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.protocols import CoreMenuItem
from infrahub.log import get_logger
from infrahub.menu.generator import generate_restricted_menu
from infrahub.menu.models import Menu  # noqa: TCH001

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.database import InfrahubDatabase


log = get_logger()
router = APIRouter(prefix="/menu")


@router.get("")
async def get_menu(
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    account_session: AccountSession = Depends(get_current_user),
) -> Menu:
    log.info("menu_request", branch=branch.name)

    menu_items = await registry.manager.query(db=db, schema=CoreMenuItem, branch=branch)
    menu = await generate_restricted_menu(db=db, branch=branch, account=account_session, menu_items=menu_items)
    return menu.to_rest()
