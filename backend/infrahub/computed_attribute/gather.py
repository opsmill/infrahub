from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from prefect import task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub import config
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreTransformPython as CoreTransformPythonNode
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase  # noqa: TC001  needed for prefect flow
from infrahub.git.utils import get_repositories_commit_per_branch
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.execution import cached_parse
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD

from .models import (
    ComputedAttrJinja2TriggerDefinition,
    ComputedAttrPythonQueryTriggerDefinition,
    ComputedAttrPythonTriggerDefinition,
    PythonTransformComputedAttribute,
)

if TYPE_CHECKING:
    from infrahub.git.models import RepositoryData


@task(
    name="gather-python-transform-attributes",
    task_run_name="Gather Python transform attributes for {branch_name}",
    cache_policy=NONE,
)
async def gather_python_transform_attributes(
    db: InfrahubDatabase, branch_name: str, repositories: dict[str, RepositoryData] | None = None
) -> list[PythonTransformComputedAttribute]:
    log = get_run_logger()
    schema_branch = registry.schema.get_schema_branch(name=branch_name)
    branches_with_diff_from_main = registry.get_altered_schema_branches()
    branch = registry.get_branch_from_registry(branch=branch_name)

    transform_attributes = schema_branch.computed_attributes.python_attributes_by_transform

    transform_names = list(transform_attributes.keys())

    if not transform_names:
        return []

    transforms = await NodeManager.query(
        db=db,
        schema=CoreTransformPythonNode,
        branch=branch_name,
        fields={"id": None, "name": None, "repository": None, "query": None},
        filters={"name__values": transform_names},
        prefetch_relationships=True,
    )

    found_transforms_names = [transform.name.value for transform in transforms]
    for transform_name in transform_names:
        if transform_name not in found_transforms_names:
            log.warning(
                msg=f"The transform {transform_name} is assigned to a computed attribute but the transform could not be found in the database."
            )
    repositories = repositories or await get_repositories_commit_per_branch(db=db)
    graphql_params = await prepare_graphql_params(db=db, branch=branch)

    computed_attributes: list[PythonTransformComputedAttribute] = []
    for transform in transforms:
        repository = await transform.repository.get_peer(db=db, raise_on_error=True)
        query = await transform.query.get_peer(db=db, raise_on_error=True)
        query_analyzer = InfrahubGraphQLQueryAnalyzer(
            query=query.query.value,
            branch=branch,
            schema_branch=schema_branch,
            schema=graphql_params.schema,
            document=cached_parse(query.query.value),
        )
        for attribute in transform_attributes[transform.name.value]:
            python_transform_computed_attribute = PythonTransformComputedAttribute(
                name=transform.name.value,
                branch_name=branch_name,
                repository_id=repository.get_id(),
                repository_name=repository.name.value,
                repository_kind=repository.get_kind(),
                query_analyzer=query_analyzer,
                query_name=query.name.value,
                query_id=query.get_id(),
                computed_attribute=attribute,
                default_schema=branch_name not in branches_with_diff_from_main,
            )
            python_transform_computed_attribute.populate_branch_commit(
                repository_data=repositories.get(repository.name.value)
            )
            computed_attributes.append(python_transform_computed_attribute)

    return computed_attributes


@task(
    name="gather-trigger-computed-attribute-jinja2",
    cache_policy=NONE,
)
async def gather_trigger_computed_attribute_jinja2(
    db: InfrahubDatabase | None = None,  # noqa: ARG001 Needed to have a common function signature for gathering functions
) -> list[ComputedAttrJinja2TriggerDefinition]:
    log = get_run_logger()

    # Build a list of all branches to process based on which branch is different from main
    branches_with_diff_from_main = registry.get_altered_schema_branches()
    branches_to_process: list[tuple[str, list[str]]] = [(branch, []) for branch in branches_with_diff_from_main]
    branches_to_process.append((registry.default_branch, branches_with_diff_from_main))

    triggers: list[ComputedAttrJinja2TriggerDefinition] = []

    for branch_scope, branches_out_of_scope in branches_to_process:
        schema_branch = registry.schema.get_schema_branch(name=branch_scope)
        mapping = schema_branch.computed_attributes.get_jinja2_trigger_nodes()

        log.info(f"Generating {len(mapping)} Jinja2 trigger for {branch_scope} (except {branches_out_of_scope})")

        for computed_attribute, trigger_nodes in mapping.items():
            for trigger_node in trigger_nodes:
                effective_trigger = trigger_node
                if trigger_node.targets_self:
                    # Self-targeting triggers use placeholder fields so they never match real
                    # NodeUpdatedEvents. The trigger definition still exists for schema-change
                    # detection in the setup flow. This matches the HFID and display label pattern.
                    effective_trigger = trigger_node.model_copy(
                        update={"attributes": [TRIGGER_PLACEHOLDER_FIELD], "relationships": []}
                    )
                trigger = ComputedAttrJinja2TriggerDefinition.from_computed_attribute(
                    branch=branch_scope,
                    computed_attribute=computed_attribute,
                    trigger_node=effective_trigger,
                    branches_out_of_scope=branches_out_of_scope,
                )
                triggers.append(trigger)

    return triggers


def _branch_scopes(branches: dict[str, PythonTransformComputedAttribute]) -> list[tuple[str, list[str]]]:
    """Which branch each automation is built for, and the branches it must not answer for.

    A branch pinned to a repository commit of its own owns an automation; the default-branch one
    covers every other branch, including the ones created after this gather.
    """
    if registry.default_branch in branches:
        commit_main = branches[registry.default_branch].repository_commit
        branches_with_diff_from_main = [
            branch_name for branch_name, item in branches.items() if item.repository_commit != commit_main
        ]
    else:
        return [(branch_name, []) for branch_name in branches]

    scopes: list[tuple[str, list[str]]] = [(branch_name, []) for branch_name in branches_with_diff_from_main]
    scopes.append((registry.default_branch, branches_with_diff_from_main))
    return scopes


@task(
    name="gather-trigger-computed-attribute-python",
    cache_policy=NONE,
)
async def gather_trigger_computed_attribute_python(
    db: InfrahubDatabase,
) -> tuple[list[ComputedAttrPythonTriggerDefinition], list[ComputedAttrPythonQueryTriggerDefinition]]:
    triggers_python = []
    triggers_python_query = []

    # Read once, so one gather cannot build some automations for one answer and some for another.
    live_only = config.SETTINGS.main.coalesce_python_recompute_after_merge

    repositories = await get_repositories_commit_per_branch(db=db)

    # Keyed by attribute and by transform: an attribute gets its own owner automation even when it
    # shares a transform, and a branch that repoints the attribute keeps a definition of its own.
    by_attribute: dict[tuple[str, str], dict[str, PythonTransformComputedAttribute]] = defaultdict(dict)
    # Keyed by transform alone: a query automation carries no attribute name, so the attributes fed
    # by one transform need one definition per read kind and not one each.
    by_transform: dict[str, dict[str, PythonTransformComputedAttribute]] = defaultdict(dict)
    for branch in list(registry.branch.values()):
        if branch.is_global:
            continue

        computed_attributes = await gather_python_transform_attributes(
            db=db, branch_name=branch.name, repositories=repositories
        )
        for computed_attribute in computed_attributes:
            key = (computed_attribute.computed_attribute.key_name, computed_attribute.name)
            by_attribute[key][branch.name] = computed_attribute
            by_transform[computed_attribute.name][branch.name] = computed_attribute

    for branches in by_attribute.values():
        for branch_scope, branches_out_of_scope in _branch_scopes(branches):
            triggers_python.append(
                ComputedAttrPythonTriggerDefinition.from_object(
                    computed_attribute=branches[branch_scope],
                    branch=branch_scope,
                    live_only=live_only,
                    branches_out_of_scope=branches_out_of_scope,
                )
            )

    for branches in by_transform.values():
        for branch_scope, branches_out_of_scope in _branch_scopes(branches):
            computed_attribute = branches[branch_scope]
            for kind, access in computed_attribute.query_analyzer.query_report.requested_read.items():
                if not access.fields:
                    # A kind reached through a generic relationship is reported for every member,
                    # even the ones the query reads no field from. Such a trigger would get no
                    # field filter and fire on every update to that kind.
                    continue

                triggers_python_query.append(
                    ComputedAttrPythonQueryTriggerDefinition.from_object(
                        kind=kind,
                        computed_attribute=computed_attribute,
                        branch=branch_scope,
                        live_only=live_only,
                        branches_out_of_scope=branches_out_of_scope,
                    )
                )

    return triggers_python, triggers_python_query
