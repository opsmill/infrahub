from __future__ import annotations

from prefect import task
from prefect.cache_policies import NONE

from infrahub.core.constants import RelationshipKind
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase  # noqa: TC001  needed for prefect flow
from infrahub.workflows.catalogue import PROFILE_REFRESH_PROCESS

from .models import ProfileRefreshTriggerDefinition


@task(name="gather-trigger-profile-refresh", cache_policy=NONE)
async def gather_trigger_profile_refresh(
    db: InfrahubDatabase | None = None,  # noqa: ARG001 Needed to have a common function signature for gathering functions
) -> list[ProfileRefreshTriggerDefinition]:
    """Gather profile refresh triggers for all profile schemas.

    This function creates trigger definitions for each profile schema that will
    listen for `NodeUpdatedEvent` on profiles. When a profile's attributes or
    relationships change, the trigger will fire and execute the profile refresh
    workflow to re-apply profiles to all related nodes.
    """
    branches_with_diff_from_main = registry.get_altered_schema_branches()
    branches_to_process: list[tuple[str, list[str]]] = [(branch, []) for branch in branches_with_diff_from_main]
    branches_to_process.append((registry.default_branch, branches_with_diff_from_main))

    triggers: list[ProfileRefreshTriggerDefinition] = []

    for branch_scope, branches_out_of_scope in branches_to_process:
        schema_branch = registry.schema.get_schema_branch(name=branch_scope)

        for profile_name in schema_branch.profile_names:
            profile_schema = schema_branch.get_profile(name=profile_name, duplicate=False)

            trigger_attr = [
                attr.name for attr in profile_schema.attributes if attr.name not in ("profile_name", "profile_priority")
            ]
            trigger_rels = [
                rel.name
                for rel in profile_schema.relationships
                if rel.kind in (RelationshipKind.GENERIC, RelationshipKind.ATTRIBUTE) and rel.name != "related_nodes"
            ]
            trigger_fields = sorted(trigger_attr + trigger_rels)

            if trigger_fields:
                triggers.append(
                    ProfileRefreshTriggerDefinition.from_profile_schema(
                        branch=branch_scope,
                        profile_kind=profile_schema.kind,
                        trigger_fields=trigger_fields,
                        workflow=PROFILE_REFRESH_PROCESS,
                        branches_out_of_scope=branches_out_of_scope,
                    )
                )

    return triggers
