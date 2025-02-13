from typing import TYPE_CHECKING

from graphene import Boolean, DateTime, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.path import NameTrackingId
from infrahub.core.diff.models import RequestDiffUpdate
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.database import retry_db_transaction
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import ValidationError
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
        if (data.from_time or data.to_time) and not data.name:
            raise ValidationError("diff with specified time range requires a name")

        component_registry = get_component_registry()
        base_branch = await registry.get_branch(db=context.db, branch=registry.default_branch)
        diff_branch = await registry.get_branch(db=context.db, branch=data.branch)
        diff_repository = await component_registry.get_component(DiffRepository, db=context.db, branch=diff_branch)

        tracking_id = NameTrackingId(name=data.name)
        existing_diffs_metatdatas = await diff_repository.get_roots_metadata(
            diff_branch_names=[diff_branch.name], base_branch_names=[base_branch.name], tracking_id=tracking_id
        )
        if existing_diffs_metatdatas:
            metadata = existing_diffs_metatdatas[0]
            from_time = Timestamp(from_timestamp_str) if from_timestamp_str else None
            to_time = Timestamp(to_timestamp_str) if to_timestamp_str else None
            branched_from_timestamp = Timestamp(diff_branch.get_branched_from())
            if from_time and from_time > metadata.from_time:
                raise ValidationError(f"from_time must be null or less than or equal to {metadata.from_time}")
            if from_time and from_time < branched_from_timestamp:
                raise ValidationError(f"from_time must be null or greater than or equal to {branched_from_timestamp}")
            if to_time and to_time < metadata.to_time:
                raise ValidationError(f"to_time must be null or greater than or equal to {metadata.to_time}")

        if data.wait_for_completion is True:
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
