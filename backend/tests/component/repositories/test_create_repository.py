from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.exceptions import WorkerTimeoutError
from infrahub.repositories.create_repository import RepositoryFinalizer
from infrahub.services import InfrahubServices
from tests.adapters.message_bus import NeverReplyingBus, UnreachableBrokerBus
from tests.adapters.workflow import WorkflowRecorder

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreGenericRepository
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_post_create_removes_the_repository_when_no_worker_answers(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="unreachable-repo", location="https://mock/unreachable.git")
    await repository.save(db=db)

    workflow = WorkflowRecorder()
    account_session = AccountSession(account_id="", auth_type=AuthType.NONE, authenticated=False)
    services = await InfrahubServices.new(database=db, message_bus=NeverReplyingBus(rpc_timeout=1), workflow=workflow)

    with pytest.raises(
        WorkerTimeoutError, match=r"^No worker answered git\.repository\.connectivity within 1 seconds$"
    ):
        await RepositoryFinalizer(
            account_session=account_session,
            services=services,
            context=InfrahubContext(branch=BranchContext(name=default_branch.name), account=account_session),
        ).post_create(
            obj=cast("CoreGenericRepository", repository),
            branch=default_branch,
            db=db,
        )

    assert await NodeManager.get_many(db=db, ids=[repository.id]) == {}
    assert workflow.submit_calls == []


async def test_post_create_removes_the_repository_when_the_broker_is_unreachable(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="unbrokered-repo", location="https://mock/unbrokered.git")
    await repository.save(db=db)

    workflow = WorkflowRecorder()
    account_session = AccountSession(account_id="", auth_type=AuthType.NONE, authenticated=False)
    services = await InfrahubServices.new(database=db, message_bus=UnreachableBrokerBus(), workflow=workflow)

    with pytest.raises(ConnectionResetError, match=r"^broker went away$"):
        await RepositoryFinalizer(
            account_session=account_session,
            services=services,
            context=InfrahubContext(branch=BranchContext(name=default_branch.name), account=account_session),
        ).post_create(
            obj=cast("CoreGenericRepository", repository),
            branch=default_branch,
            db=db,
        )

    assert await NodeManager.get_many(db=db, ids=[repository.id]) == {}
    assert workflow.submit_calls == []
