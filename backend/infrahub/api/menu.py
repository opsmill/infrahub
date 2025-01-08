from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from infrahub.api.dependencies import get_branch_dep, get_db, get_permission_manager
from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TC001
from infrahub.core.protocols import CoreMenuItem
from infrahub.log import get_logger
from infrahub.menu.generator import generate_restricted_menu
from infrahub.menu.models import Menu  # noqa: TC001

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions import PermissionManager


log = get_logger()
router = APIRouter(prefix="/menu")


@router.get("")
async def get_menu(
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    permission_manager: PermissionManager = Depends(get_permission_manager),
) -> Menu:
    log.info("menu_request", branch=branch.name)

    menu_items = await registry.manager.query(db=db, schema=CoreMenuItem, branch=branch, prefetch_relationships=True)
    menu = await generate_restricted_menu(
        db=db, branch=branch, menu_items=menu_items, account_permissions=permission_manager
    )
    return menu.to_rest()
