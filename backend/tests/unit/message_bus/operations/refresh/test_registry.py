from uuid import uuid4

from infrahub.core.branch import Branch
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase
from infrahub.message_bus import Meta, messages
from infrahub.message_bus.operations.refresh.registry import rebased_branch
from infrahub.services import InfrahubServices
from tests.adapters.message_bus import BusSimulator


async def test_rebased_branch(db: InfrahubDatabase):
    """Validate that a deleted branch triggers a registry refresh and cancels open proposed changes"""

    branch_name = "test_rebased_branch"
    branch = Branch(name=branch_name)
    await branch.save(db=db)
    message = messages.RefreshRegistryRebasedBranch(branch=branch_name, meta=Meta(initiator_id=str(uuid4())))

    recorder = BusSimulator()
    service = InfrahubServices(database=db, message_bus=recorder)
    assert branch_name not in registry.branch
    await rebased_branch(message=message, service=service)
    assert branch_name in registry.branch
