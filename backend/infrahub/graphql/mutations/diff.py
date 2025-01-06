from typing import TYPE_CHECKING

from graphene import Boolean, DateTime, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.models import RequestDiffUpdate
from infrahub.database import retry_db_transaction
from infrahub.dependencies.registry import get_component_registry
from infrahub.workflows.catalogue import DIFF_UPDATE

if TYPE_CHECKING:
    from ..initialization import GraphqlContext


class DiffUpdateInput(InputObjectType):
    branch = String(required=True)
    name = String(required=False)
    from_time = DateTime(required=False)
    to_time = DateTime(required=False)
    wait_for_completion = Boolean(required=False)


class DiffUpdateMutation(Mutation):
    class Arguments:
        data = DiffUpdateInput(required=True)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="diff_update")
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: DiffUpdateInput,
    ) -> dict[str, bool]:
        context: GraphqlContext = info.context

        from_timestamp_str = DateTime.serialize(data.from_time) if data.from_time else None
        to_timestamp_str = DateTime.serialize(data.to_time) if data.to_time else None
        if data.wait_for_completion is True:
            component_registry = get_component_registry()
            base_branch = await registry.get_branch(db=context.db, branch=registry.default_branch)
            diff_branch = await registry.get_branch(db=context.db, branch=data.branch)

            diff_coordinator = await component_registry.get_component(
                DiffCoordinator, db=context.db, branch=diff_branch
            )
            await diff_coordinator.run_update(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=from_timestamp_str,
                to_time=to_timestamp_str,
                name=data.name,
            )

            return {"ok": True}

        model = RequestDiffUpdate(
            branch_name=str(data.branch),
            name=data.name,
            from_time=from_timestamp_str,
            to_time=to_timestamp_str,
        )
        if context.service:
            await context.service.workflow.submit_workflow(workflow=DIFF_UPDATE, parameters={"model": model})

        return {"ok": True}
