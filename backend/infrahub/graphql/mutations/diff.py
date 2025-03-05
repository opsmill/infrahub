from typing import TYPE_CHECKING

from graphene import Boolean, DateTime, Field, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.path import NameTrackingId
from infrahub.core.diff.models import RequestDiffUpdate
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import ValidationError
from infrahub.graphql.context import apply_external_context
from infrahub.graphql.types.context import ContextInput
from infrahub.workflows.catalogue import DIFF_UPDATE

from ..types.task import TaskInfo

if TYPE_CHECKING:
    from ..initialization import GraphqlContext


class DiffUpdateInput(InputObjectType):
    branch = String(required=True)
    name = String(required=False)
    from_time = DateTime(required=False)
    to_time = DateTime(required=False)
    wait_for_completion = Boolean(required=False, deprecation_reason="Please use `wait_until_completion` instead")


class DiffUpdateMutation(Mutation):
    class Arguments:
        data = DiffUpdateInput(required=True)
        context = ContextInput(required=False)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: DiffUpdateInput,
        context: ContextInput | None = None,
        wait_until_completion: bool = False,
    ) -> dict[str, bool | dict[str, str]]:
        graphql_context: GraphqlContext = info.context
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        if data.wait_for_completion is True:
            wait_until_completion = True

        from_timestamp_str = DateTime.serialize(data.from_time) if data.from_time else None
        to_timestamp_str = DateTime.serialize(data.to_time) if data.to_time else None
        if (data.from_time or data.to_time) and not data.name:
            raise ValidationError("diff with specified time range requires a name")

        component_registry = get_component_registry()
        base_branch = await registry.get_branch(db=graphql_context.db, branch=registry.default_branch)
        diff_branch = await registry.get_branch(db=graphql_context.db, branch=data.branch)
        diff_repository = await component_registry.get_component(
            DiffRepository, db=graphql_context.db, branch=diff_branch
        )

        tracking_id = NameTrackingId(name=data.name)
        existing_diffs_metadatas = await diff_repository.get_roots_metadata(
            diff_branch_names=[diff_branch.name], base_branch_names=[base_branch.name], tracking_id=tracking_id
        )
        if existing_diffs_metadatas:
            metadata = existing_diffs_metadatas[0]
            from_time = Timestamp(from_timestamp_str) if from_timestamp_str else None
            to_time = Timestamp(to_timestamp_str) if to_timestamp_str else None
            branched_from_timestamp = Timestamp(diff_branch.get_branched_from())
            if from_time and from_time > metadata.from_time:
                raise ValidationError(f"from_time must be null or less than or equal to {metadata.from_time}")
            if from_time and from_time < branched_from_timestamp:
                raise ValidationError(f"from_time must be null or greater than or equal to {branched_from_timestamp}")
            if to_time and to_time < metadata.to_time:
                raise ValidationError(f"to_time must be null or greater than or equal to {metadata.to_time}")

        if wait_until_completion is True:
            diff_coordinator = await component_registry.get_component(
                DiffCoordinator, db=graphql_context.db, branch=diff_branch
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
        if graphql_context.service:
            workflow = await graphql_context.service.workflow.submit_workflow(
                workflow=DIFF_UPDATE, parameters={"model": model}
            )
            return {"ok": True, "task": {"id": str(workflow.id)}}

        return {"ok": True}
