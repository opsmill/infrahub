from __future__ import annotations

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.core.recompute.bulk_write import HFID_FIELD, AttributeValueWrite
from infrahub.core.recompute.dispatch import build_bulk_recompute_dispatcher
from infrahub.core.registry import registry
from infrahub.events import BranchDeletedEvent
from infrahub.events.models import EventContext  # noqa: TC001  needed for prefect flow
from infrahub.trigger.models import TriggerSetupReport, TriggerType
from infrahub.trigger.setup import setup_triggers_specific
from infrahub.workers.dependencies import get_client, get_component, get_database, get_workflow
from infrahub.workflows.catalogue import HFID_PROCESS, TRIGGER_UPDATE_HFID
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .gather import gather_trigger_hfid
from .graphql_queries import HFIDNodeIDQuery
from .models import HFIDGraphQL, HFIDTriggerDefinition


@flow(
    name="hfid-process",
    flow_run_name="Process human friendly ids for {target_kind}",
)
async def process_hfid(
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
        log.debug("No object id provided for human-friendly id recompute")
        return

    await add_tags(branches=[branch_name])

    target_schema = branch_name if branch_name in registry.get_altered_schema_branches() else registry.default_branch
    schema_branch = registry.schema.get_schema_branch(name=target_schema)
    node_schema = schema_branch.get_node(name=target_kind, duplicate=False)

    if node_kind == target_kind:
        hfid_definition = schema_branch.hfids.get_node_definition(kind=node_kind)
    else:
        hfid_definition = schema_branch.hfids.get_related_definition(related_kind=node_kind, target_kind=target_kind)

    hfid_graphql = HFIDGraphQL(
        node_schema=node_schema, variables=hfid_definition.hfid, filter_key=hfid_definition.filter_key
    )

    query = hfid_graphql.render_graphql_query(filter_id=filter_id)
    response = await client.execute_graphql(query=query, branch_name=branch_name)
    update_candidates = hfid_graphql.parse_response(response=response)

    if not update_candidates:
        log.debug("No nodes found that requires updates")
        return

    writes: list[AttributeValueWrite] = []
    for node in update_candidates:
        rendered_hfid = [node.variables[component] for component in hfid_definition.hfid if component in node.variables]
        if rendered_hfid != node.hfid_value:
            writes.append(AttributeValueWrite(node_id=node.node_id, field=HFID_FIELD, value=rendered_hfid))

    dispatcher = await build_bulk_recompute_dispatcher(schema_branch=schema_branch)
    await dispatcher.dispatch(
        writes=writes,
        branch_name=branch_name,
        context=context,
        coalesced=object_ids is not None,
        recompute_depth=recompute_depth,
    )


@flow(name="hfid-setup", flow_run_name="Setup human friendly ids in task-manager")
async def hfid_setup(context: EventContext, branch_name: str | None = None, event_name: str | None = None) -> None:
    database = await get_database()
    async with database.start_session() as db:
        log = get_run_logger()

        if branch_name:
            await add_tags(branches=[branch_name])
            component = await get_component()
            await wait_for_schema_to_converge(branch_name=branch_name, component=component, db=db, log=log)

        report: TriggerSetupReport = await setup_triggers_specific(
            gatherer=gather_trigger_hfid, trigger_type=TriggerType.HUMAN_FRIENDLY_ID
        )

        # Configure all DisplayLabelTriggerDefinitions in Prefect
        all_triggers = report.triggers_with_type(trigger_type=HFIDTriggerDefinition)
        direct_target_triggers = [
            hfid_report
            for hfid_report in report.modified_triggers_with_type(trigger_type=HFIDTriggerDefinition)
            if hfid_report.target_kind
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
                        and default_branch_triggers[0].hfid_hash == display_report.hfid_hash
                    ):
                        log.debug(
                            f"Skipping HFID updates for {display_report.target_kind} [{branch_name}], schema is identical to default branch"
                        )
                        continue

                await get_workflow().submit_workflow(
                    workflow=TRIGGER_UPDATE_HFID,
                    context=context,
                    parameters={
                        "branch_name": display_report.branch,
                        "kind": display_report.target_kind,
                    },
                )

        log.info(f"{report.in_use_count} HFID automation configurations completed")


@flow(
    name="trigger-update-hfid",
    flow_run_name="Trigger updates for HFID for {kind}",
)
async def trigger_update_hfid(
    branch_name: str,
    kind: str,
    context: EventContext,
) -> None:
    await add_tags(branches=[branch_name])

    client = get_client()

    node_query = HFIDNodeIDQuery(kind=kind)
    workflow = get_workflow()
    async for node_batch in node_query.fetch_all_paginated(client=client, branch_name=branch_name):
        for node_id in node_batch:
            await workflow.submit_workflow(
                workflow=HFID_PROCESS,
                context=context,
                parameters={
                    "branch_name": branch_name,
                    "node_kind": kind,
                    "target_kind": kind,
                    "object_id": node_id,
                    "context": context,
                },
            )
