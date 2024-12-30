from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Boolean, InputField, InputObjectType, Mutation, String

from infrahub.core.constants import BranchConflictKeep, InfrahubKind
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.manager import NodeManager
from infrahub.database import retry_db_transaction
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import ProcessingError
from infrahub.graphql.enums import ConflictSelection as GraphQlConflictSelection

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from ..initialization import GraphqlContext


# pylint: disable=unused-argument


class ResolveDiffConflictInput(InputObjectType):
    conflict_id = InputField(String(required=True), description="ID of the diff conflict to resolve")
    selected_branch = InputField(
        GraphQlConflictSelection(required=True), description="Which version of the conflict to select"
    )


class ResolveDiffConflict(Mutation):
    class Arguments:
        data = ResolveDiffConflictInput(required=True)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="resolve_diff_conflict")
    async def mutate(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: ResolveDiffConflictInput,
    ) -> ResolveDiffConflict:
        context: GraphqlContext = info.context

        component_registry = get_component_registry()
        diff_repo = await component_registry.get_component(DiffRepository, db=context.db, branch=context.branch)

        selection = ConflictSelection(data.selected_branch.value) if data.selected_branch else None
        conflict = await diff_repo.get_conflict_by_id(conflict_id=data.conflict_id)
        if conflict.resolvable is False:
            raise ProcessingError("Conflict must be resolved manually on conflicting branch(es)")
        await diff_repo.update_conflict_by_id(conflict_id=data.conflict_id, selection=selection)

        core_data_checks = await NodeManager.query(
            db=context.db, schema=InfrahubKind.DATACHECK, filters={"enriched_conflict_id__value": data.conflict_id}
        )
        if not core_data_checks:
            return cls(ok=True)
        if data.selected_branch is GraphQlConflictSelection.BASE_BRANCH:
            keep_branch = BranchConflictKeep.TARGET
        elif data.selected_branch is GraphQlConflictSelection.DIFF_BRANCH:
            keep_branch = BranchConflictKeep.SOURCE
        else:
            keep_branch = None
        for cdc in core_data_checks:
            cdc.keep_branch.value = keep_branch
            await cdc.save(db=context.db)
        return cls(ok=True)
