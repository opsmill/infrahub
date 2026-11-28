from __future__ import annotations

from infrahub_sdk.template.exceptions import JinjaTemplateError
from prefect import flow
from prefect.client.orchestration import get_client as get_prefect_client
from prefect.logging import get_run_logger

from infrahub.computed_attribute.jinja2 import InfrahubJinja2Template
from infrahub.core.constants.schema import DISPLAY_LABEL_ATTRIBUTE_NAME
from infrahub.core.recompute.bulk_write import AttributeValueWrite
from infrahub.core.recompute.dispatch import build_bulk_recompute_dispatcher
from infrahub.core.registry import registry
from infrahub.core.template_fingerprint.collector import collect_schema_fingerprints
from infrahub.core.template_fingerprint.models import TemplateFamily
from infrahub.core.template_fingerprint.refresher import TemplateFingerprintRefresher
from infrahub.core.template_fingerprint.repository import TemplateFingerprintRepository
from infrahub.display_labels.graphql_queries import DisplayLabelNodeIDQuery
from infrahub.events import BranchDeletedEvent
from infrahub.events.limits import get_submission_chunk_size
from infrahub.events.models import EventContext  # noqa: TC001  needed for prefect flow
from infrahub.trigger.models import TriggerSetupReport, TriggerType
from infrahub.trigger.placeholder_carry_over import carry_over_placeholder_fingerprints
from infrahub.trigger.setup import setup_triggers, trigger_configuration_lock
from infrahub.workers.dependencies import get_client, get_component, get_database, get_workflow
from infrahub.workflows.catalogue import DISPLAY_LABELS_PROCESS_JINJA2, TRIGGER_UPDATE_DISPLAY_LABELS
from infrahub.workflows.constants import WorkflowTag
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .gather import gather_trigger_display_labels_jinja2
from .models import (
    DisplayLabelJinja2GraphQL,
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
    client.request_context = context.to_request_context()

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
        try:
            value = await jinja_template.render(variables=node.variables)
        except JinjaTemplateError as exc:
            log.warning(f"Skipping display label recompute for node {node.node_id}: template raised {exc}")
            continue
        if value != node.display_label_value:
            writes.append(AttributeValueWrite(node_id=node.node_id, field=DISPLAY_LABEL_ATTRIBUTE_NAME, value=value))

    dispatcher = await build_bulk_recompute_dispatcher(schema_branch=schema_branch, coalesced=object_ids is not None)
    await dispatcher.dispatch(
        writes=writes,
        branch_name=branch_name,
        context=context,
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

        repository = TemplateFingerprintRepository(db=db)
        refresher = TemplateFingerprintRefresher(
            family=TemplateFamily.DISPLAY_LABEL_JINJA2,
            default_branch=registry.default_branch,
            repository=repository,
            workflow=get_workflow(),
            recompute_workflow=TRIGGER_UPDATE_DISPLAY_LABELS,
        )
        async with trigger_configuration_lock(trigger_type=TriggerType.DISPLAY_LABEL_JINJA2):
            triggers = await gather_trigger_display_labels_jinja2()
            async with get_prefect_client(sync_client=False) as prefect_client:
                report: TriggerSetupReport = await setup_triggers(
                    client=prefect_client, triggers=triggers, trigger_type=TriggerType.DISPLAY_LABEL_JINJA2
                )
            schema = collect_schema_fingerprints(family=TemplateFamily.DISPLAY_LABEL_JINJA2)
            await carry_over_placeholder_fingerprints(deleted=report.deleted, schemas=[schema], repository=repository)
            decision = await refresher.refresh(
                schema=schema,
                event_branch=branch_name,
                branch_deleted=event_name == BranchDeletedEvent.event_name,
                context=context,
            )

        if decision.skipped_identical:
            log.debug(
                f"Skipping display label updates for {decision.skipped_identical} [{branch_name}], "
                "template identical to default branch"
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
    client.request_context = context.to_request_context()

    node_query = DisplayLabelNodeIDQuery(kind=kind)
    workflow = get_workflow()
    async for node_ids in node_query.fetch_all_chunked(
        client=client, branch_name=branch_name, chunk_size=get_submission_chunk_size()
    ):
        await workflow.submit_workflow(
            workflow=DISPLAY_LABELS_PROCESS_JINJA2,
            context=context,
            parameters={
                "branch_name": branch_name,
                "node_kind": kind,
                "target_kind": kind,
                "object_ids": node_ids,
                "context": context,
            },
            # Must be a creation tag: in-flow tag updates drop tags added mid-run.
            tags=[WorkflowTag.BRANCH.render(identifier=branch_name)],
        )
