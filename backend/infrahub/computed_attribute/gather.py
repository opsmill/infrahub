from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from infrahub_sdk import InfrahubClient  # noqa: TC002  needed for prefect flow
from infrahub_sdk.protocols import (
    CoreTransformPython,
)
from prefect import task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub.core.registry import registry

from .models import (
    ComputedAttrJinja2TriggerDefinition,
    ComputedAttrPythonQueryTriggerDefinition,
    ComputedAttrPythonTriggerDefinition,
    PythonTransformComputedAttribute,
)

if TYPE_CHECKING:
    from infrahub_sdk.data import RepositoryData


@task(
    name="gather-python-transform-attributes",
    task_run_name="Gather Python transform attributes for {branch_name}",
    cache_policy=NONE,
)
async def gather_python_transform_attributes(
    branch_name: str, client: InfrahubClient, repositories: dict[str, RepositoryData] | None = None
) -> list[PythonTransformComputedAttribute]:
    log = get_run_logger()
    schema_branch = registry.schema.get_schema_branch(name=branch_name)
    branches_with_diff_from_main = registry.get_altered_schema_branches()

    transform_attributes = schema_branch.computed_attributes.python_attributes_by_transform

    transform_names = list(transform_attributes.keys())
    if not transform_names:
        return []

    transforms = await client.filters(
        kind=CoreTransformPython,
        branch=branch_name,
        prefetch_relationships=True,
        populate_store=True,
        name__values=transform_names,
    )

    found_transforms_names = [transform.name.value for transform in transforms]
    for transform_name in transform_names:
        if transform_name not in found_transforms_names:
            log.warning(
                msg=f"The transform {transform_name} is assigned to a computed attribute but the transform could not be found in the database."
            )
    repositories = repositories or await client.get_list_repositories()

    computed_attributes: list[PythonTransformComputedAttribute] = []
    for transform in transforms:
        for attribute in transform_attributes[transform.name.value]:
            python_transform_computed_attribute = PythonTransformComputedAttribute(
                name=transform.name.value,
                branch_name=branch_name,
                repository_id=transform.repository.peer.id,
                repository_name=transform.repository.peer.name.value,
                repository_kind=transform.repository.peer.typename,
                query_name=transform.query.peer.name.value,
                query_models=transform.query.peer.models.value,
                computed_attribute=attribute,
                default_schema=branch_name not in branches_with_diff_from_main,
            )
            python_transform_computed_attribute.populate_branch_commit(
                repository_data=repositories.get(transform.repository.peer.name.value)
            )
            computed_attributes.append(python_transform_computed_attribute)

    return computed_attributes


@task(
    name="gather-trigger-computed-attribute-jinja2",
    cache_policy=NONE,
)
async def gather_trigger_computed_attribute_jinja2() -> list[ComputedAttrJinja2TriggerDefinition]:
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
                trigger = ComputedAttrJinja2TriggerDefinition.from_computed_attribute(
                    branch=branch_scope,
                    computed_attribute=computed_attribute,
                    trigger_node=trigger_node,
                    branches_out_of_scope=branches_out_of_scope,
                )
                triggers.append(trigger)

    return triggers


@task(
    name="gather-trigger-computed-attribute-python",
    cache_policy=NONE,
)
async def gather_trigger_computed_attribute_python(
    client: InfrahubClient,
) -> tuple[list[ComputedAttrPythonTriggerDefinition], list[ComputedAttrPythonQueryTriggerDefinition]]:
    triggers_python = []
    triggers_python_query = []

    repositories = await client.get_list_repositories()

    all_computed_attributes: dict[str, dict[str, PythonTransformComputedAttribute]] = defaultdict(dict)
    for branch in list(registry.branch.values()):
        computed_attributes = await gather_python_transform_attributes(
            branch_name=branch.name, client=client, repositories=repositories
        )
        for computed_attribute in computed_attributes:
            all_computed_attributes[computed_attribute.name][branch.name] = computed_attribute

    for branches in all_computed_attributes.values():
        branches_with_diff_from_main = []
        if registry.default_branch in branches.keys():
            commit_main = branches[registry.default_branch].repository_commit
            branches_with_diff_from_main = [
                branch_name for branch_name, item in branches.items() if item.repository_commit != commit_main
            ]
        else:
            branches_with_diff_from_main = list(branches.keys())

        branches_to_process: list[tuple[str, list[str]]] = [(branch, []) for branch in branches_with_diff_from_main]
        branches_to_process.append((registry.default_branch, branches_with_diff_from_main))

        for branch_scope, branches_out_of_scope in branches_to_process:
            trigger_python = ComputedAttrPythonTriggerDefinition.from_object(
                computed_attribute=branches[branch_scope],
                branch=branch_scope,
                branches_out_of_scope=branches_out_of_scope,
            )
            triggers_python.append(trigger_python)

            trigger_python_query = ComputedAttrPythonQueryTriggerDefinition.from_object(
                computed_attribute=branches[branch_scope],
                branch=branch_scope,
                branches_out_of_scope=branches_out_of_scope,
            )
            triggers_python_query.append(trigger_python_query)

    return triggers_python, triggers_python_query
