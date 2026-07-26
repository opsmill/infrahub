from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.exceptions import URLNotFoundError
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.client.orchestration import get_client as get_prefect_client
from prefect.logging import get_run_logger

from infrahub import lock
from infrahub.core.constants import ComputedAttributeKind, InfrahubKind, MutationAction
from infrahub.core.recompute.bulk_write import AttributeValueWrite
from infrahub.core.recompute.dispatch import build_bulk_recompute_dispatcher
from infrahub.core.registry import registry
from infrahub.core.schema.schema_branch_computed import TransformReadSet
from infrahub.events import BranchDeletedEvent
from infrahub.events.limits import get_submission_chunk_size
from infrahub.events.models import EventContext  # noqa: TC001  needed for prefect flow
from infrahub.events.schema_action import ChangedElementsPayload  # noqa: TC001  needed for prefect flow
from infrahub.git.repository import get_initialized_repo
from infrahub.trigger.models import TriggerSetupReport, TriggerType
from infrahub.trigger.setup import setup_triggers, setup_triggers_specific
from infrahub.workers.dependencies import get_client, get_component, get_database, get_workflow
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
    TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
)
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .gather import gather_trigger_computed_attribute_jinja2, gather_trigger_computed_attribute_python
from .graphql_queries.queries import ComputedAttributeNodeIDQuery, ComputedAttributeTransformQuery
from .jinja2 import InfrahubJinja2Template
from .models import (
    ComputedAttrJinja2GraphQL,
    ComputedAttrJinja2GraphQLResponse,
    ComputedAttrJinja2TriggerDefinition,
    PythonTransformTarget,
)
from .scoping import (
    ChangedElementSet,
    ComputedAttributeRef,
    Jinja2DependencyDeriver,
    PythonTransformDependencyDeriver,
    RecomputeScoper,
)
from .transform_recompute import TransformRecomputeSubmitter

if TYPE_CHECKING:
    from infrahub.core.schema.computed_attribute import ComputedAttribute
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.analyzer import GraphQLQueryReport


def _chunk_ids(ids: list[str], chunk_size: int) -> list[list[str]]:
    return [ids[i : i + chunk_size] for i in range(0, len(ids), chunk_size)]


async def _reconcile_python_computed_attribute_automations(db: InfrahubDatabase) -> None:
    """Reconcile the node-input (data-path) automations against the current schema.

    One gather builds both trigger lists and they are applied under a single trigger-registry
    lock, so a concurrent reconcile cannot delete an automation another run just created.
    """
    log = get_run_logger()
    async with lock.registry.get(
        name="configure-action-rules-computed-attr-python", namespace="trigger-rules", local=False
    ):
        triggers_python, triggers_python_query = await gather_trigger_computed_attribute_python(db=db)
        async with get_prefect_client(sync_client=False) as prefect_client:
            await setup_triggers(
                client=prefect_client, triggers=triggers_python, trigger_type=TriggerType.COMPUTED_ATTR_PYTHON
            )
            await setup_triggers(
                client=prefect_client,
                triggers=triggers_python_query,
                trigger_type=TriggerType.COMPUTED_ATTR_PYTHON_QUERY,
            )
    log.debug("Reconciled Python computed-attribute node-input automations")


UPDATE_ATTRIBUTE = """
mutation UpdateAttribute(
    $id: String!,
    $kind: String!,
    $attribute: String!,
    $value: String!
    $context_account_id: String!
  ) {
  InfrahubUpdateComputedAttribute(
    context: {account: {id: $context_account_id}},
    data: {id: $id, attribute: $attribute, value: $value, kind: $kind}
  ) {
    ok
  }
}
"""


def _resolve_changed_elements(
    changed_elements: ChangedElementsPayload | None,
) -> ChangedElementSet | None:
    """Normalize the workflow parameter into the internal change set.

    ``None`` signals that no change set was available and recompute must fall back
    to processing every attribute. Prefect deserializes the JSON workflow parameter
    into ``ChangedElementsPayload`` at the flow boundary, so consumers see either
    the model or ``None``.
    """
    if changed_elements is None:
        return None
    return ChangedElementSet.from_payload(changed_elements)


def _transform_read_set_from_query_report(report: GraphQLQueryReport) -> TransformReadSet:
    """Map an analyzed GraphQL query report into the kinds and fields it reads."""
    return TransformReadSet.from_read_fields({kind: access.fields for kind, access in report.requested_read.items()})


@task(name="computed-attribute-process-transform-for-node", cache_policy=NONE)
async def process_transform_for_node(
    branch_name: str,
    object_id: str,
    node_kind: str,
    attribute_name: str,
    query_id: str,
    transform_timeout: int | None,
    repository_id: str,
    repository_name: str,
    repository_kind: str,
    commit: str | None,
    file_path: str,
    class_name: str,
    convert_query_response: bool,
    context: EventContext,
) -> None:
    client = get_client()
    client.request_context = context.to_request_context()

    repo = await get_initialized_repo(
        client=client,
        repository_id=repository_id,
        name=repository_name,
        repository_kind=repository_kind,
        commit=commit,
    )

    data = await client.query_gql_query(
        name=query_id,
        branch_name=branch_name,
        variables={"id": object_id},
        update_group=True,
        subscribers=[object_id],
    )

    transformed_data = await repo.execute_python_transform.with_options(timeout_seconds=transform_timeout)(
        client=client,
        branch_name=branch_name,
        commit=commit,
        location=f"{file_path}::{class_name}",
        data=data,
        convert_query_response=convert_query_response,
    )  # type: ignore[call-overload]

    await client.execute_graphql(
        query=UPDATE_ATTRIBUTE,
        variables={
            "id": object_id,
            "kind": node_kind,
            "attribute": attribute_name,
            "value": transformed_data,
            "context_account_id": context.account_id,
        },
        branch_name=branch_name,
    )


@flow(
    name="computed_attribute_process_transform",
    flow_run_name="Process computed attribute for {computed_attribute_kind}.{computed_attribute_name}",
)
async def process_transform(
    branch_name: str,
    node_kind: str,
    computed_attribute_name: str,  # noqa: ARG001
    computed_attribute_kind: str,  # noqa: ARG001
    context: EventContext,
    object_id: str | None = None,
    object_ids: list[str] | None = None,
    updated_fields: list[str] | None = None,  # noqa: ARG001
) -> None:
    all_ids = list({*([object_id] if object_id else []), *(object_ids or [])})
    await add_tags(branches=[branch_name], nodes=all_ids)
    client = get_client()
    client.request_context = context.to_request_context()

    schema_branch = registry.schema.get_schema_branch(name=branch_name)
    node_schema = schema_branch.get_node(name=node_kind, duplicate=False)
    transform_attributes: dict[str, ComputedAttribute] = {}
    for attribute in node_schema.attributes:
        if attribute.computed_attribute and attribute.computed_attribute.kind == ComputedAttributeKind.TRANSFORM_PYTHON:
            transform_attributes[attribute.name] = attribute.computed_attribute

    if not transform_attributes:
        return

    for attribute_name, transform_attribute in transform_attributes.items():
        if not transform_attribute.transform:
            raise ValueError(f"No transform configured for computed attribute '{attribute_name}'")
        transform_query = ComputedAttributeTransformQuery(transform_id=transform_attribute.transform)
        transform_response = await client.execute_graphql(
            query=transform_query.render_query(),
            variables=transform_query.get_variables(),
            branch_name=branch_name,
        )
        transform = transform_query.parse_response(response=transform_response)

        if not transform:
            raise ValueError(
                f"Unable to fetch transform '{transform_attribute.transform}' for computed attribute '{attribute_name}'"
            )

        batch = await client.create_batch()
        for oid in all_ids:
            batch.add(
                task=process_transform_for_node,
                branch_name=branch_name,
                object_id=oid,
                node_kind=node_kind,
                attribute_name=attribute_name,
                query_id=transform.query_name,
                transform_timeout=transform.timeout,
                repository_id=transform.repository_id,
                repository_name=transform.repository_name,
                repository_kind=transform.repository_typename,
                commit=transform.repository_commit,
                file_path=transform.file_path,
                class_name=transform.class_name,
                convert_query_response=transform.convert_query_response,
                context=context,
            )
        _ = [r async for _, r in batch.execute()]


@flow(
    name="trigger_update_python_computed_attributes",
    flow_run_name="Trigger updates for computed attributes on branch {branch_name} for {computed_attribute_kind}.{computed_attribute_name}",
)
async def trigger_update_python_computed_attributes(
    branch_name: str,
    computed_attribute_name: str,
    computed_attribute_kind: str,
    context: EventContext,
) -> None:
    await add_tags(branches=[branch_name])

    client = get_client()
    client.request_context = context.to_request_context()
    nodes = await client.all(kind=computed_attribute_kind, branch=branch_name)
    object_ids = [node.id for node in nodes]

    if not object_ids:
        return

    chunk_size = get_submission_chunk_size()
    for chunk in _chunk_ids(object_ids, chunk_size):
        await get_workflow().submit_workflow(
            workflow=COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
            context=context,
            parameters={
                "branch_name": branch_name,
                "node_kind": computed_attribute_kind,
                "object_ids": chunk,
                "computed_attribute_name": computed_attribute_name,
                "computed_attribute_kind": computed_attribute_kind,
                "context": context,
            },
        )


@flow(
    name="computed_attribute_process_jinja2",
    flow_run_name="Process computed attribute for {computed_attribute_kind}.{computed_attribute_name}",
)
async def process_jinja2(
    branch_name: str,
    node_kind: str,
    computed_attribute_name: str,
    computed_attribute_kind: str,
    context: EventContext,
    object_id: str | None = None,
    updated_fields: list[str] | None = None,
    object_ids: list[str] | None = None,
    recompute_depth: int = 0,
) -> None:
    """Recompute a single Jinja2 computed attribute in response to a node mutation.

    The live trigger passes a single ``object_id``; the coalesced merge/rebase recompute passes
    the union of changed node ids in ``object_ids``. ``computed_attribute_kind`` differs from
    ``node_kind`` when the dependency crosses a relationship.
    """
    log = get_run_logger()
    client = get_client()
    client.request_context = context.to_request_context()

    filter_id: str | list[str] | None = object_ids if object_ids is not None else object_id
    if not filter_id:
        log.debug("No object id provided for computed attribute recompute")
        return

    await add_tags(branches=[branch_name])
    updates: list[str] = updated_fields or []

    target_branch_schema = (
        branch_name if branch_name in registry.get_altered_schema_branches() else registry.default_branch
    )
    schema_branch = registry.schema.get_schema_branch(name=target_branch_schema)
    node_schema = schema_branch.get_node(name=computed_attribute_kind, duplicate=False)
    resolved_targets = [
        resolved
        for resolved in schema_branch.computed_attributes.get_impacted_jinja2_targets(kind=node_kind, updates=updates)
        if resolved.target.kind == computed_attribute_kind and resolved.target.attribute.name == computed_attribute_name
    ]
    writes: list[AttributeValueWrite] = []
    for resolved in resolved_targets:
        found: list[ComputedAttrJinja2GraphQLResponse] = []
        template_string = "n/a"
        attribute = resolved.target.attribute
        if attribute.computed_attribute and attribute.computed_attribute.jinja2_template:
            template_string = attribute.computed_attribute.jinja2_template

        jinja_template = InfrahubJinja2Template(template=template_string)
        variables = jinja_template.get_variables()

        attribute_graphql = ComputedAttrJinja2GraphQL(
            node_schema=node_schema, attribute_schema=attribute, variables=variables
        )

        for id_filter in resolved.node_filters:
            query = attribute_graphql.render_graphql_query(query_filter=id_filter, filter_id=filter_id)
            try:
                response = await client.execute_graphql(query=query, branch_name=branch_name)
            except URLNotFoundError:
                log.warning(
                    f"Process computed attributes for {computed_attribute_kind}.{computed_attribute_name} failed for branch {branch_name} (not found)"
                )
                return
            output = attribute_graphql.parse_response(response=response)
            found.extend(output)

        if not found:
            log.debug("No nodes found that requires updates")

        for node in found:
            value = await jinja_template.render(variables=node.variables)
            if value != node.computed_attribute_value:
                writes.append(AttributeValueWrite(node_id=node.node_id, field=attribute.name, value=value))

    dispatcher = await build_bulk_recompute_dispatcher(schema_branch=schema_branch)
    await dispatcher.dispatch(
        writes=writes,
        branch_name=branch_name,
        context=context,
        coalesced=object_ids is not None,
        recompute_depth=recompute_depth,
    )


@flow(
    name="trigger_update_jinja2_computed_attributes",
    flow_run_name="Trigger updates for computed attributes for {computed_attribute_kind}.{computed_attribute_name}",
)
async def trigger_update_jinja2_computed_attributes(
    branch_name: str,
    computed_attribute_name: str,
    computed_attribute_kind: str,
    context: EventContext,
) -> None:
    await add_tags(branches=[branch_name])

    client = get_client()
    client.request_context = context.to_request_context()

    node_query = ComputedAttributeNodeIDQuery(kind=computed_attribute_kind)
    workflow = get_workflow()
    async for node_batch in node_query.fetch_all_paginated(client=client, branch_name=branch_name):
        for node_id in node_batch:
            await workflow.submit_workflow(
                workflow=COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
                context=context,
                parameters={
                    "branch_name": branch_name,
                    "computed_attribute_name": computed_attribute_name,
                    "computed_attribute_kind": computed_attribute_kind,
                    "node_kind": computed_attribute_kind,
                    "object_id": node_id,
                    "context": context,
                },
            )


@flow(name="computed-attribute-setup-jinja2", flow_run_name="Setup computed attributes in task-manager")
async def computed_attribute_setup_jinja2(
    context: EventContext,
    branch_name: str | None = None,
    event_name: str | None = None,
    changed_elements: ChangedElementsPayload | None = None,
) -> None:
    database = await get_database()
    async with database.start_session() as db:
        log = get_run_logger()

        changed_element_set = _resolve_changed_elements(changed_elements)
        branch_name = branch_name or registry.default_branch

        if branch_name:
            await add_tags(branches=[branch_name])
            component = await get_component()
            await wait_for_schema_to_converge(branch_name=branch_name, component=component, db=db, log=log)

        report: TriggerSetupReport = await setup_triggers_specific(
            gatherer=gather_trigger_computed_attribute_jinja2, trigger_type=TriggerType.COMPUTED_ATTR_JINJA2
        )
        # Configure all ComputedAttrJinja2Trigger in Prefect

        all_triggers = report.triggers_with_type(trigger_type=ComputedAttrJinja2TriggerDefinition)

        # The self-targeting triggers are the per (kind, attribute) recompute units.
        self_triggers_on_branch = [
            trigger for trigger in all_triggers if trigger.targets_self and trigger.branch == branch_name
        ]

        if changed_element_set is None:
            # No change set is available, so fall back to recomputing every computed attribute on
            # the branch rather than risk leaving a value stale.
            candidate_triggers = self_triggers_on_branch
        else:
            # The change set is available, so scope across every self-targeting attribute:
            # a template edit, a read-field change, or a relationship-reached change all select it.
            schema_branch = registry.schema.get_schema_branch(name=branch_name)
            jinja2_trigger_nodes = {
                (target.kind, target.attribute.name): trigger_nodes
                for target, trigger_nodes in schema_branch.computed_attributes.get_jinja2_trigger_nodes().items()
            }
            scoper = RecomputeScoper(
                derivers={ComputedAttributeKind.JINJA2: Jinja2DependencyDeriver(trigger_nodes=jinja2_trigger_nodes)}
            )
            triggers_by_ref = {
                ComputedAttributeRef(
                    branch=trigger.branch,
                    kind=trigger.computed_attribute.kind,
                    attribute_name=trigger.computed_attribute.attribute.name,
                    computed_kind=ComputedAttributeKind.JINJA2,
                ): trigger
                for trigger in self_triggers_on_branch
            }
            scoping_report = scoper.scope(
                candidate_attributes=list(triggers_by_ref.keys()),
                changed_elements=changed_element_set,
            )
            selected_identities = [f"{ref.kind}.{ref.attribute_name}" for ref in scoping_report.selected]
            log.info(
                f"Recompute scoping selected {len(scoping_report.selected)} Jinja2 computed attribute(s) on "
                f"{branch_name}: {selected_identities}"
            )
            for skipped in scoping_report.skipped:
                log.debug(
                    f"Skipping {skipped.ref.kind}.{skipped.ref.attribute_name} on {branch_name}: {skipped.reason}"
                )
            candidate_triggers = [triggers_by_ref[ref] for ref in scoping_report.selected]

        for candidate_trigger in candidate_triggers:
            if event_name != BranchDeletedEvent.event_name and candidate_trigger.branch == branch_name:
                if branch_name != registry.default_branch:
                    default_branch_triggers = [
                        trigger
                        for trigger in all_triggers
                        if trigger.branch == registry.default_branch
                        and trigger.targets_self
                        and trigger.computed_attribute.kind == candidate_trigger.computed_attribute.kind
                        and trigger.computed_attribute.attribute.name
                        == candidate_trigger.computed_attribute.attribute.name
                    ]
                    if (
                        default_branch_triggers
                        and len(default_branch_triggers) == 1
                        and default_branch_triggers[0].template_hash == candidate_trigger.template_hash
                    ):
                        log.debug(
                            f"Skipping computed attribute updates for {candidate_trigger.computed_attribute.kind}."
                            f"{candidate_trigger.computed_attribute.attribute.name} [{branch_name}], schema is identical to default branch"
                        )
                        continue

                await get_workflow().submit_workflow(
                    workflow=TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
                    context=context,
                    parameters={
                        "branch_name": candidate_trigger.branch,
                        "computed_attribute_name": candidate_trigger.computed_attribute.attribute.name,
                        "computed_attribute_kind": candidate_trigger.computed_attribute.kind,
                    },
                )

        log.info(f"{report.in_use_count} Computed Attribute for Jinja2 automation configuration completed")


@flow(
    name="computed-attribute-setup-python",
    flow_run_name="Setup computed attributes for Python transforms in task-manager",
)
async def computed_attribute_setup_python(
    context: EventContext,
    branch_name: str | None = None,
    event_name: str | None = None,
    commit: str | None = None,  # noqa: ARG001
    changed_elements: ChangedElementsPayload | None = None,
) -> None:
    database = await get_database()
    async with database.start_session() as db:
        log = get_run_logger()

        changed_element_set = _resolve_changed_elements(changed_elements)

        branch_name = branch_name or registry.default_branch
        if branch_name:
            await add_tags(branches=[branch_name])
            component = await get_component()
            await wait_for_schema_to_converge(branch_name=branch_name, component=component, db=db, log=log)

        triggers_python, _ = await gather_trigger_computed_attribute_python(db=db)

        # The read set of each transform is derived from its GraphQL query here, where the
        # database session is available, so that the scoping decision itself stays pure.
        read_sets: dict[tuple[str, str, str], TransformReadSet] = {}
        for trigger in triggers_python:
            definition = trigger.computed_attribute.computed_attribute
            read_sets[trigger.branch, definition.kind, definition.attribute.name] = (
                _transform_read_set_from_query_report(report=trigger.computed_attribute.query_analyzer.query_report)
            )

        # Since we can have multiple trigger per NodeKind
        # we need to extract the list of unique node that should be processed
        unique_nodes: set[tuple[str, str, str]] = {
            (
                trigger.branch,
                trigger.computed_attribute.computed_attribute.kind,
                trigger.computed_attribute.computed_attribute.attribute.name,
            )
            for trigger in triggers_python
        }
        candidate_attributes = [
            ComputedAttributeRef(
                branch=branch,
                kind=kind,
                attribute_name=attribute_name,
                computed_kind=ComputedAttributeKind.TRANSFORM_PYTHON,
            )
            for branch, kind, attribute_name in sorted(unique_nodes)
            if event_name != BranchDeletedEvent.event_name and branch == branch_name
        ]

        scoper = RecomputeScoper(
            derivers={ComputedAttributeKind.TRANSFORM_PYTHON: PythonTransformDependencyDeriver(read_sets=read_sets)}
        )
        report = scoper.scope(
            candidate_attributes=candidate_attributes,
            changed_elements=changed_element_set,
        )

        selected_identities = [f"{ref.kind}.{ref.attribute_name}" for ref in report.selected]
        log.info(
            f"Recompute scoping selected {len(report.selected)} Python computed attribute(s) on {branch_name}: "
            f"{selected_identities}"
        )
        for skipped in report.skipped:
            log.debug(f"Skipping {skipped.ref.kind}.{skipped.ref.attribute_name} on {branch_name}: {skipped.reason}")

        for ref in report.selected:
            await get_workflow().submit_workflow(
                workflow=TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
                context=context,
                parameters={
                    "branch_name": branch_name,
                    "computed_attribute_name": ref.attribute_name,
                    "computed_attribute_kind": ref.kind,
                },
            )

        await _reconcile_python_computed_attribute_automations(db=db)


@flow(
    name="computed-attribute-process-transform-lifecycle",
    flow_run_name="Process computed attributes for transform {transform_id} lifecycle ({action})",
)
async def process_transform_lifecycle(
    branch_name: str,
    transform_id: str,
    action: str,
    context: EventContext,
    event_name: str | None = None,  # noqa: ARG001  passed by the trigger, kept for the flow contract
) -> None:
    """React to a Python transform's own lifecycle event.

    A create or fingerprint change recomputes the attributes it feeds; every event also
    reconciles the node-input automations, so a delete drops the gone transform's automation.
    """
    log = get_run_logger()
    await add_tags(branches=[branch_name], nodes=[transform_id])

    database = await get_database()
    async with database.start_session() as db:
        try:
            if action in {MutationAction.CREATED.value, MutationAction.UPDATED.value}:
                # The transform -> attribute wiring lives in the schema, which a worker other than
                # the importer may not have caught up on yet; wait so the map is not read empty.
                component = await get_component()
                await wait_for_schema_to_converge(branch_name=branch_name, component=component, db=db, log=log)

                submitter = TransformRecomputeSubmitter(client=get_client(), workflow=get_workflow())
                await submitter.submit(branch_name=branch_name, transform_id=transform_id, context=context)
        finally:
            # Reconcile on every event, even when the recompute leg above failed, so a transform-only
            # import builds the node-input automations and a delete drops the removed transform's one.
            await _reconcile_python_computed_attribute_automations(db=db)


@flow(
    name="query-computed-attribute-transform-targets",
    flow_run_name="Query for potential targets of computed attributes for {node_kind}",
)
async def query_transform_targets(
    branch_name: str,
    node_kind: str,  # noqa: ARG001
    object_id: str,
    context: EventContext,
) -> None:
    await add_tags(branches=[branch_name])
    schema_branch = registry.schema.get_schema_branch(name=branch_name)
    client = get_client()
    client.request_context = context.to_request_context()
    targets = await client.execute_graphql(
        query=GATHER_GRAPHQL_QUERY_SUBSCRIBERS, variables={"members": [object_id]}, branch_name=branch_name
    )

    subscribers: list[PythonTransformTarget] = []

    for group in targets[InfrahubKind.GRAPHQLQUERYGROUP]["edges"]:
        for subscriber in group["node"]["subscribers"]["edges"]:
            subscribers.append(
                PythonTransformTarget(object_id=subscriber["node"]["id"], kind=subscriber["node"]["__typename"])
            )

    nodes_with_computed_attributes = schema_branch.computed_attributes.get_python_attributes_per_node()

    # Group by (kind, attribute_name) so each attribute gets one batch workflow submission
    batches: dict[tuple[str, str], list[str]] = {}
    for subscriber in subscribers:
        if subscriber.kind in nodes_with_computed_attributes:
            for computed_attribute in nodes_with_computed_attributes[subscriber.kind]:
                key = (subscriber.kind, computed_attribute.name)
                batches.setdefault(key, []).append(subscriber.object_id)

    chunk_size = get_submission_chunk_size()
    for (kind, attribute_name), batch_object_ids in batches.items():
        for chunk in _chunk_ids(batch_object_ids, chunk_size):
            await get_workflow().submit_workflow(
                workflow=COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
                context=context,
                parameters={
                    "branch_name": branch_name,
                    "node_kind": kind,
                    "object_ids": chunk,
                    "computed_attribute_name": attribute_name,
                    "computed_attribute_kind": kind,
                    "context": context,
                },
            )


GATHER_GRAPHQL_QUERY_SUBSCRIBERS = """
query GatherGraphQLQuerySubscribers($members: [ID!]) {
  CoreGraphQLQueryGroup(members__ids: $members) {
    edges {
      node {
        subscribers {
          edges {
            node {
              id
              __typename
            }
          }
        }
      }
    }
  }
}
"""
