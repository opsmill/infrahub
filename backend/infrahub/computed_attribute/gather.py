from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from prefect import task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericRepository, CoreGraphQLQuery
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase  # noqa: TC001  needed for prefect flow
from infrahub.git.utils import get_repositories_commit_per_branch
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import prepare_graphql_params

from .models import (
    ComputedAttrJinja2TriggerDefinition,
    ComputedAttrPythonQueryTriggerDefinition,
    ComputedAttrPythonTriggerDefinition,
    PythonTransformComputedAttribute,
)

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreTransformPython as CoreTransformPythonNode
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

    transforms: list[CoreTransformPythonNode] = await NodeManager.query(
        db=db,
        schema=InfrahubKind.TRANSFORMPYTHON,
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
        repository = await transform.repository.get_peer(db=db, peer_type=CoreGenericRepository, raise_on_error=True)
        query = await transform.query.get_peer(db=db, peer_type=CoreGraphQLQuery, raise_on_error=True)
        query_analyzer = InfrahubGraphQLQueryAnalyzer(
            query=query.query.value,
            branch=branch,
            schema_branch=schema_branch,
            schema=graphql_params.schema,
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
    db: InfrahubDatabase,
) -> tuple[list[ComputedAttrPythonTriggerDefinition], list[ComputedAttrPythonQueryTriggerDefinition]]:
    triggers_python = []
    triggers_python_query = []

    repositories = await get_repositories_commit_per_branch(db=db)

    all_computed_attributes: dict[str, dict[str, PythonTransformComputedAttribute]] = defaultdict(dict)
    for branch in list(registry.branch.values()):
        if branch.is_global:
            continue

        computed_attributes = await gather_python_transform_attributes(
            db=db, branch_name=branch.name, repositories=repositories
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

            for kind in branches[branch_scope].query_analyzer.query_report.requested_read.keys():
                trigger_python_query = ComputedAttrPythonQueryTriggerDefinition.from_object(
                    kind=kind,
                    computed_attribute=branches[branch_scope],
                    branch=branch_scope,
                    branches_out_of_scope=branches_out_of_scope,
                )
                triggers_python_query.append(trigger_python_query)

    return triggers_python, triggers_python_query
