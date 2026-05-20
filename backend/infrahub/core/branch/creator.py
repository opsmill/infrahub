from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pydantic

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.events.branch_action import BranchCreatedEvent
from infrahub.events.models import EventMeta
from infrahub.exceptions import BranchNotFoundError, ValidationError
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CREATE_BRANCH

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.mutations.models import BranchCreateModel
    from infrahub.lock import InfrahubLockRegistry
    from infrahub.services.adapters.event import InfrahubEventService
    from infrahub.services.adapters.workflow import InfrahubWorkflow
    from infrahub.services.component import InfrahubComponent


class BranchCreator:
    def __init__(
        self,
        db: InfrahubDatabase,
        lock_registry: InfrahubLockRegistry,
        component: InfrahubComponent,
        event_service: InfrahubEventService,
        workflow: InfrahubWorkflow,
    ) -> None:
        self.db = db
        self.lock_registry = lock_registry
        self.component = component
        self.event_service = event_service
        self.workflow = workflow

    async def create(self, model: BranchCreateModel, context: InfrahubContext) -> None:
        try:
            await Branch.get_by_name(db=self.db, name=model.name)
            raise ValidationError(f"The branch {model.name} already exists")
        except BranchNotFoundError:
            pass

        data_dict: dict[str, Any] = dict(model)
        data_dict.pop("is_isolated", None)

        try:
            obj = Branch(**data_dict)
        except pydantic.ValidationError as exc:
            error_msgs = [f"invalid field {error['loc'][0]}: {error['msg']}" for error in exc.errors()]
            raise ValidationError("\n".join(error_msgs)) from exc

        # distributed lock to prevent creating multiple branches with the same name
        async with self.lock_registry.get(name=model.name, namespace="branch_create", local=False):
            # Re-check existence under the lock to prevent TOCTOU race
            try:
                await Branch.get_by_name(db=self.db, name=model.name)
                raise ValidationError(f"The branch {model.name} already exists")
            except BranchNotFoundError:
                pass

            async with self.lock_registry.local_schema_lock():
                # Copy the schema from the origin branch and set the hash and the schema_changed_at value
                origin_schema = registry.schema.get_schema_branch(name=obj.origin_branch)
                new_schema = origin_schema.duplicate(name=obj.name)
                registry.schema.set_schema_branch(name=obj.name, schema=new_schema)
                obj.update_schema_hash()
                await obj.save(db=self.db, user_id=context.account.account_id)

                # Add Branch to registry
                registry.branch[obj.name] = obj
                await self.component.refresh_schema_hash(branches=[obj.name])

        event = BranchCreatedEvent(
            branch_name=obj.name,
            branch_id=str(obj.uuid),
            sync_with_git=obj.sync_with_git,
            meta=EventMeta.from_context(context=context.to_event_context(), branch=registry.get_global_branch()),
        )
        await self.event_service.send(event=event)

        if obj.sync_with_git:
            await self.workflow.submit_workflow(
                workflow=GIT_REPOSITORIES_CREATE_BRANCH,
                context=context,
                parameters={"branch": obj.name, "branch_id": str(obj.uuid)},
            )
