from __future__ import annotations

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.computed_attribute.jinja2 import InfrahubJinja2Template
from infrahub.core.recompute.bulk_write import DISPLAY_LABEL_FIELD, AttributeValueWrite
from infrahub.core.recompute.dispatch import persist_and_chain
from infrahub.core.registry import registry
from infrahub.display_labels.graphql_queries import DisplayLabelNodeIDQuery
from infrahub.events import BranchDeletedEvent
from infrahub.events.models import EventContext  # noqa: TC001  needed for prefect flow
from infrahub.trigger.models import TriggerSetupReport, TriggerType
from infrahub.trigger.setup import setup_triggers_specific
from infrahub.workers.dependencies import get_client, get_component, get_database, get_workflow
from infrahub.workflows.catalogue import DISPLAY_LABELS_PROCESS_JINJA2, TRIGGER_UPDATE_DISPLAY_LABELS
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .gather import gather_trigger_display_labels_jinja2
from .models import (
    DisplayLabelJinja2GraphQL,
    DisplayLabelTriggerDefinition,
)


@flow(
    name="display-label-process-jinja2",
    flow_run_name="Process display_labels for {target_kind}",
)
async def process_display_label(
    branch_name: str,
    node_kind: str,
    target_kind: str,
    context: EventContext,
    object_id: str | None = None,
    object_ids: list[str] | None = None,
    recompute_depth: int = 0,
) -> None:
    log = get_run_logger()
    client = get_client()

    filter_id: str | list[str] | None = object_ids if object_ids is not None else object_id
    if not filter_id:
        log.debug("No object id provided for display label recompute")
        return

    await add_tags(branches=[branch_name])

    target_schema = branch_name if branch_name in registry.get_altered_schema_branches() else registry.default_branch
    schema_branch = registry.schema.get_schema_branch(name=target_schema)
    node_schema = schema_branch.get_node(name=target_kind, duplicate=False)

    if node_kind == target_kind:
        display_label_template = schema_branch.display_labels.get_template_node(kind=node_kind)
    else:
        display_label_template = schema_branch.display_labels.get_related_template(
            related_kind=node_kind, target_kind=target_kind
        )

    jinja_template = InfrahubJinja2Template(template=display_label_template.template)
    variables = jinja_template.get_variables()
    display_label_graphql = DisplayLabelJinja2GraphQL(
        node_schema=node_schema, variables=variables, filter_key=display_label_template.filter_key
    )

    query = display_label_graphql.render_graphql_query(filter_id=filter_id)
    response = await client.execute_graphql(query=query, branch_name=branch_name)
    update_candidates = display_label_graphql.parse_response(response=response)

    if not update_candidates:
        log.debug("No nodes found that requires updates")
        return

    writes: list[AttributeValueWrite] = []
    for node in update_candidates:
        value = await jinja_template.render(variables=node.variables)
        if value != node.display_label_value:
            writes.append(AttributeValueWrite(node_id=node.node_id, field=DISPLAY_LABEL_FIELD, value=value))

    await persist_and_chain(
        writes=writes,
        schema_branch=schema_branch,
        branch_name=branch_name,
        context=context,
        coalesced=object_ids is not None,
        recompute_depth=recompute_depth,
    )


@flow(name="display-labels-setup-jinja2", flow_run_name="Setup display labels in task-manager")
async def display_labels_setup_jinja2(
    context: EventContext, branch_name: str | None = None, event_name: str | None = None
) -> None:
    database = await get_database()
    async with database.start_session() as db:
        log = get_run_logger()

        if branch_name:
            await add_tags(branches=[branch_name])
            component = await get_component()
            await wait_for_schema_to_converge(branch_name=branch_name, component=component, db=db, log=log)

        report: TriggerSetupReport = await setup_triggers_specific(
            gatherer=gather_trigger_display_labels_jinja2, trigger_type=TriggerType.DISPLAY_LABEL_JINJA2
        )

        # Configure all DisplayLabelTriggerDefinitions in Prefect
        all_triggers = report.triggers_with_type(trigger_type=DisplayLabelTriggerDefinition)
        direct_target_triggers = [
            display_report
            for display_report in report.modified_triggers_with_type(trigger_type=DisplayLabelTriggerDefinition)
            if display_report.target_kind
        ]

        for display_report in direct_target_triggers:
            if event_name != BranchDeletedEvent.event_name and display_report.branch == branch_name:
                if branch_name != registry.default_branch:
                    default_branch_triggers = [
                        trigger
                        for trigger in all_triggers
                        if trigger.branch == registry.default_branch
                        and trigger.target_kind == display_report.target_kind
                    ]
                    if (
                        default_branch_triggers
                        and len(default_branch_triggers) == 1
                        and default_branch_triggers[0].template_hash == display_report.template_hash
                    ):
                        log.debug(
                            f"Skipping display label updates for {display_report.target_kind} [{branch_name}], schema is identical to default branch"
                        )
                        continue

                await get_workflow().submit_workflow(
                    workflow=TRIGGER_UPDATE_DISPLAY_LABELS,
                    context=context,
                    parameters={
                        "branch_name": display_report.branch,
                        "kind": display_report.target_kind,
                    },
                )

        log.info(f"{report.in_use_count} Display labels for Jinja2 automation configuration completed")


@flow(
    name="trigger-update-display-labels",
    flow_run_name="Trigger updates for display labels for {kind}",
)
async def trigger_update_display_labels(
    branch_name: str,
    kind: str,
    context: EventContext,
) -> None:
    await add_tags(branches=[branch_name])

    client = get_client()

    node_query = DisplayLabelNodeIDQuery(kind=kind)
    workflow = get_workflow()
    async for node_batch in node_query.fetch_all_paginated(client=client, branch_name=branch_name):
        for node_id in node_batch:
            await workflow.submit_workflow(
                workflow=DISPLAY_LABELS_PROCESS_JINJA2,
                context=context,
                parameters={
                    "branch_name": branch_name,
                    "node_kind": kind,
                    "target_kind": kind,
                    "object_id": node_id,
                    "context": context,
                },
            )
