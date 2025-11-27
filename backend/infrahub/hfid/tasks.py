from __future__ import annotations

from infrahub_sdk.exceptions import URLNotFoundError
from prefect import flow
from prefect.logging import get_run_logger

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core.registry import registry
from infrahub.events import BranchDeletedEvent
from infrahub.trigger.models import TriggerSetupReport, TriggerType
from infrahub.trigger.setup import setup_triggers_specific
from infrahub.workers.dependencies import get_client, get_component, get_database, get_workflow
from infrahub.workflows.catalogue import HFID_PROCESS, TRIGGER_UPDATE_HFID
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .gather import gather_trigger_hfid
from .models import HFIDGraphQL, HFIDGraphQLResponse, HFIDTriggerDefinition

UPDATE_HFID = """
mutation UpdateHFID(
    $id: String!,
    $kind: String!,
    $value: [String!]!
  ) {
  InfrahubUpdateHFID(
    data: {id: $id, value: $value, kind: $kind}
  ) {
    ok
  }
}
"""


@flow(
    name="hfid-update-value",
    flow_run_name="Update value for hfid on {node_kind}",
)
async def hfid_update_value(
    branch_name: str,
    obj: HFIDGraphQLResponse,
    node_kind: str,
    hfid_definition: list[str],
) -> None:
    log = get_run_logger()
    client = get_client()

    await add_tags(branches=[branch_name], nodes=[obj.node_id], db_change=True)

    rendered_hfid: list[str] = []
    for hfid_component in hfid_definition:
        if hfid_component in obj.variables:
            rendered_hfid.append(obj.variables[hfid_component])
    # value = await template.render(variables=obj.variables)
    if rendered_hfid == obj.hfid_value:
        log.debug(f"Ignoring to update {obj} with existing value on human_friendly_id={obj.hfid_value}")
        return

    try:
        await client.execute_graphql(
            query=UPDATE_HFID,
            variables={"id": obj.node_id, "kind": node_kind, "value": rendered_hfid},
            branch_name=branch_name,
        )
        log.info(f"Updating {node_kind}.human_friendly_id='{rendered_hfid}' ({obj.node_id})")
    except URLNotFoundError:
        log.warning(
            f"Updating {node_kind}.human_friendly_id='{rendered_hfid}' ({obj.node_id}) failed for branch {branch_name} (branch not found)"
        )


@flow(
    name="hfid-process",
    flow_run_name="Process human friendly ids for {target_kind}",
)
async def process_hfid(
    branch_name: str,
    node_kind: str,
    object_id: str,
    target_kind: str,
    context: InfrahubContext,  # noqa: ARG001
) -> None:
    log = get_run_logger()
    client = get_client()

    await add_tags(branches=[branch_name])

    target_schema = branch_name if branch_name in registry.get_altered_schema_branches() else registry.default_branch
    schema_branch = registry.schema.get_schema_branch(name=target_schema)
    node_schema = schema_branch.get_node(name=target_kind, duplicate=False)

    if node_kind == target_kind:
        hfid_definition = schema_branch.hfids.get_node_definition(kind=node_kind)
    else:
        hfid_definition = schema_branch.hfids.get_related_definition(related_kind=node_kind, target_kind=target_kind)

    # jinja_template = Jinja2Template(template=display_label_template.template)
    # variables = jinja_template.get_variables()
    hfid_graphql = HFIDGraphQL(
        node_schema=node_schema, variables=hfid_definition.hfid, filter_key=hfid_definition.filter_key
    )

    query = hfid_graphql.render_graphql_query(filter_id=object_id)
    response = await client.execute_graphql(query=query, branch_name=branch_name)
    update_candidates = hfid_graphql.parse_response(response=response)

    if not update_candidates:
        log.debug("No nodes found that requires updates")
        return

    batch = await client.create_batch()
    for node in update_candidates:
        batch.add(
            task=hfid_update_value,
            branch_name=branch_name,
            obj=node,
            node_kind=node_schema.kind,
            hfid_definition=hfid_definition.hfid,
        )

    _ = [response async for _, response in batch.execute()]


@flow(name="hfid-setup", flow_run_name="Setup human friendly ids in task-manager")
async def hfid_setup(context: InfrahubContext, branch_name: str | None = None, event_name: str | None = None) -> None:
    database = await get_database()
    async with database.start_session() as db:
        log = get_run_logger()

        if branch_name:
            await add_tags(branches=[branch_name])
            component = await get_component()
            await wait_for_schema_to_converge(branch_name=branch_name, component=component, db=db, log=log)

        report: TriggerSetupReport = await setup_triggers_specific(
            gatherer=gather_trigger_hfid, trigger_type=TriggerType.HUMAN_FRIENDLY_ID
        )  # type: ignore[misc]

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
    context: InfrahubContext,
) -> None:
    await add_tags(branches=[branch_name])

    client = get_client()

    # NOTE we only need the id of the nodes, this query will still query for the HFID
    node_schema = registry.schema.get_node_schema(name=kind, branch=branch_name)
    nodes = await client.all(
        kind=kind,
        branch=branch_name,
        exclude=node_schema.attribute_names + node_schema.relationship_names,
        populate_store=False,
    )

    for node in nodes:
        await get_workflow().submit_workflow(
            workflow=HFID_PROCESS,
            context=context,
            parameters={
                "branch_name": branch_name,
                "node_kind": kind,
                "target_kind": kind,
                "object_id": node.id,
                "context": context,
            },
        )
