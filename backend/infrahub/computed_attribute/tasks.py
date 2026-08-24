from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.exceptions import URLNotFoundError
from prefect import flow
from prefect.client.orchestration import get_client as get_prefect_client
from prefect.logging import get_run_logger

from infrahub import lock
from infrahub.core.constants import ComputedAttributeKind, MutationAction
from infrahub.core.query_group.subscribers import fetch_subscriber_refs
from infrahub.core.recompute.bulk_write import AttributeValueWrite
from infrahub.core.recompute.dispatch import build_bulk_recompute_dispatcher
from infrahub.core.registry import registry
from infrahub.events import BranchDeletedEvent
from infrahub.events.limits import get_submission_chunk_size
from infrahub.events.models import EventContext  # noqa: TC001  needed for prefect flow
from infrahub.events.schema_action import ChangedElementsPayload  # noqa: TC001  needed for prefect flow
from infrahub.git.repository import get_initialized_repo
from infrahub.trigger.models import TriggerSetupReport, TriggerType
from infrahub.trigger.setup import setup_triggers, setup_triggers_specific
from infrahub.utilities.chunks import chunked
from infrahub.workers.dependencies import get_client, get_component, get_database, get_workflow
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
    TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
)
from infrahub.workflows.constants import WorkflowTag
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
from .read_sets import transform_read_set_from_query_report
from .scoping import (
    ChangedElementSet,
    ComputedAttributeRef,
    Jinja2DependencyDeriver,
    PythonTransformDependencyDeriver,
    RecomputeScoper,
)
from .transform_recompute import TransformRecomputeSubmitter

if TYPE_CHECKING:
    from infrahub.core.schema import NodeSchema
    from infrahub.core.schema.computed_attribute import ComputedAttribute
    from infrahub.core.schema.schema_branch_computed import TransformReadSet
    from infrahub.database import InfrahubDatabase
    from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository


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


def _python_transform_attributes(*, node_schema: NodeSchema, attribute_name: str) -> dict[str, ComputedAttribute]:
    """The Python transform computed attributes of a kind, narrowed to the requested one.

    Every caller submits one flow per attribute, so processing the whole kind here would run the
    transform of a kind with N attributes N times per submission.
    """
    transform_attributes = {
        attribute.name: attribute.computed_attribute
        for attribute in node_schema.attributes
        if attribute.computed_attribute and attribute.computed_attribute.kind == ComputedAttributeKind.TRANSFORM_PYTHON
    }
    requested = transform_attributes.get(attribute_name)
    return {attribute_name: requested} if requested else {}


async def _transform_value_for_node(
    *,
    branch_name: str,
    object_id: str,
    attribute_name: str,
    query_id: str,
    transform_timeout: int | None,
    commit: str | None,
    file_path: str,
    class_name: str,
    convert_query_response: bool,
    context: EventContext,
    repo: InfrahubReadOnlyRepository | InfrahubRepository,
) -> AttributeValueWrite:
    """Compute one node's value against a shared, pre-initialized repository.

    ``update_group`` keeps the node subscribed to the transform's query group, which is
    what routes future source changes back to this node. ``context`` is reapplied here
    because ``get_client()`` builds a fresh client per call rather than inheriting one.
    """
    client = get_client()
    client.request_context = context.to_request_context()

    data = await client.query_gql_query(
        name=query_id,
        branch_name=branch_name,
        variables={"id": object_id},
        update_group=True,
        subscribers=[object_id],
    )

    value = await repo.execute_python_transform.with_options(timeout_seconds=transform_timeout)(
        client=client,
        branch_name=branch_name,
        commit=commit,
        location=f"{file_path}::{class_name}",
        data=data,
        convert_query_response=convert_query_response,
    )  # type: ignore[call-overload]

    return AttributeValueWrite(node_id=object_id, field=attribute_name, value=value)


def _partition_transform_results(
    results: list[tuple[str, AttributeValueWrite | Exception]],
) -> tuple[list[AttributeValueWrite], list[tuple[str, str]]]:
    """Split results into values to persist and ``(node_id, reason)`` skips.

    A raised or non-string result is skipped so one bad node cannot block its siblings,
    and a failure never overwrites the last good value with null.
    """
    writes: list[AttributeValueWrite] = []
    skipped: list[tuple[str, str]] = []
    for object_id, result in results:
        if isinstance(result, Exception):
            skipped.append((object_id, f"transform raised {result!r}"))
        elif not isinstance(result.value, str):
            skipped.append((object_id, f"transform returned {type(result.value).__name__}, expected a string"))
        else:
            writes.append(result)
    return writes, skipped


@flow(
    name="computed_attribute_process_transform",
    flow_run_name="Process computed attribute for {computed_attribute_kind}.{computed_attribute_name}",
)
async def process_transform(
    branch_name: str,
    node_kind: str,
    computed_attribute_name: str,
    computed_attribute_kind: str,  # noqa: ARG001
    context: EventContext,
    object_id: str | None = None,
    object_ids: list[str] | None = None,
    updated_fields: list[str] | None = None,  # noqa: ARG001
    coalesced: bool = False,
    recompute_depth: int = 0,
) -> None:
    """Recompute one Python computed attribute for a batch of nodes.

    One repository init and one bulk write per batch; unchanged values emit no events
    and fan out no further recompute; a failing node keeps its previous value without
    blocking its siblings. A coalesced pass stamps its writes with the recompute origin
    and drives the next level through the bounded chain, instead of letting the writes
    re-enter the live per-node paths.

    Raises:
        ValueError: if a computed attribute has no transform configured or the transform cannot be fetched.

    """
    log = get_run_logger()
    all_ids = list({*([object_id] if object_id else []), *(object_ids or [])})
    await add_tags(branches=[branch_name], nodes=all_ids)
    if not all_ids:
        return
    client = get_client()
    client.request_context = context.to_request_context()

    schema_branch = registry.schema.get_schema_branch(name=branch_name)
    node_schema = schema_branch.get_node(name=node_kind, duplicate=False)
    transform_attributes = _python_transform_attributes(node_schema=node_schema, attribute_name=computed_attribute_name)

    if not transform_attributes:
        log.warning(f"'{node_kind}' has no Python computed attribute named '{computed_attribute_name}'")
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

        repo = await get_initialized_repo(
            client=client,
            repository_id=transform.repository_id,
            name=transform.repository_name,
            repository_kind=transform.repository_typename,
            commit=transform.repository_commit,
        )

        # One failing node must not abort the batch and drop its siblings' writes.
        batch = await client.create_batch(return_exceptions=True)
        for oid in all_ids:
            batch.add(
                task=_transform_value_for_node,
                node=oid,
                branch_name=branch_name,
                object_id=oid,
                attribute_name=attribute_name,
                query_id=transform.query_name,
                transform_timeout=transform.timeout,
                commit=transform.repository_commit,
                file_path=transform.file_path,
                class_name=transform.class_name,
                convert_query_response=transform.convert_query_response,
                context=context,
                repo=repo,
            )
        results: list[tuple[str, AttributeValueWrite | Exception]] = [
            (oid, result) async for oid, result in batch.execute()
        ]
        writes, skipped = _partition_transform_results(results)
        for skipped_id, reason in skipped:
            log.warning(f"Skipping recompute of '{attribute_name}' for node {skipped_id}: {reason}")

        dispatcher = await build_bulk_recompute_dispatcher(schema_branch=schema_branch)
        await dispatcher.dispatch(
            writes=writes,
            branch_name=branch_name,
            context=context,
            coalesced=coalesced,
            recompute_depth=recompute_depth,
        )
        log.info(
            f"Recompute of '{attribute_name}' complete: submitted={len(results)} "
            f"written={len(writes)} skipped={len(skipped)}"
        )


@flow(
    name="trigger_update_python_computed_attributes",
    flow_run_name="Trigger updates for computed attributes on branch {branch_name} for {computed_attribute_kind}.{computed_attribute_name}",
)
async def trigger_update_python_computed_attributes(
    branch_name: str,
    computed_attribute_name: str,
    computed_attribute_kind: str,
    context: EventContext,
    coalesced: bool = False,
    recompute_depth: int = 0,
) -> None:
    """Recompute one Python computed attribute over every node of its kind.

    ``coalesced`` and ``recompute_depth`` are carried to each batch, so a widened pass keeps the
    recompute origin and the depth bound of the pass that asked for it.
    """
    await add_tags(branches=[branch_name])

    client = get_client()
    client.request_context = context.to_request_context()
    nodes = await client.all(kind=computed_attribute_kind, branch=branch_name)
    object_ids = [node.id for node in nodes]

    if not object_ids:
        return

    chunk_size = get_submission_chunk_size()
    for chunk in chunked(object_ids, chunk_size):
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
                "coalesced": coalesced,
                "recompute_depth": recompute_depth,
            },
            # Must be a creation tag: in-flow tag updates drop tags added mid-run.
            tags=[WorkflowTag.BRANCH.render(identifier=branch_name)],
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
        # database session is available, so that the scoping decision itself stays pure. A
        # derived read is checked against the schema of the trigger's own branch, whose derived
        # definitions are what decide the read can be held against a single kind.
        read_sets: dict[tuple[str, str, str], TransformReadSet] = {}
        for trigger in triggers_python:
            definition = trigger.computed_attribute.computed_attribute
            read_sets[trigger.branch, definition.kind, definition.attribute.name] = (
                transform_read_set_from_query_report(
                    report=trigger.computed_attribute.query_analyzer.query_report,
                    schema_branch=registry.schema.get_schema_branch(name=trigger.branch),
                )
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
    refs = await fetch_subscriber_refs(client=client, node_ids=[object_id], branch=branch_name)
    subscribers = [PythonTransformTarget(object_id=ref.id, kind=ref.kind) for ref in refs]

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
        for chunk in chunked(batch_object_ids, chunk_size):
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
                # Must be a creation tag: in-flow tag updates drop tags added mid-run.
                tags=[WorkflowTag.BRANCH.render(identifier=branch_name)],
            )
