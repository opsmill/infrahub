from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.template_fingerprint.decision import decide_fingerprint_changes

if TYPE_CHECKING:
    from infrahub.core.template_fingerprint.models import FingerprintDecision, SchemaFingerprints, TemplateFamily
    from infrahub.core.template_fingerprint.repository import TemplateFingerprintRepository
    from infrahub.events.models import EventContext
    from infrahub.services.adapters.workflow import InfrahubWorkflow
    from infrahub.workflows.models import WorkflowDefinition


class TemplateFingerprintRefresher:
    """Submit one recompute per kind whose template changed on the event branch, then record its fingerprint.

    The caller holds the configuration lock of the family, so two runs never read the same records.
    """

    def __init__(
        self,
        family: TemplateFamily,
        default_branch: str,
        repository: TemplateFingerprintRepository,
        workflow: InfrahubWorkflow,
        recompute_workflow: WorkflowDefinition,
    ) -> None:
        self.family = family
        self.default_branch = default_branch
        self.repository = repository
        self.workflow = workflow
        self.recompute_workflow = recompute_workflow

    async def refresh(
        self, schema: SchemaFingerprints, event_branch: str | None, branch_deleted: bool, context: EventContext
    ) -> FingerprintDecision:
        """Apply the recompute decision; a submission that raises leaves the records unchanged so the next run retries."""
        decision = decide_fingerprint_changes(
            family=self.family,
            event_branch=event_branch,
            branch_deleted=branch_deleted,
            default_branch=self.default_branch,
            schema=schema,
            recorded=await self.repository.get_by_family(family=self.family),
        )

        await self.repository.delete(keys=decision.to_delete)
        for kind in decision.to_recompute:
            await self.workflow.submit_workflow(
                workflow=self.recompute_workflow,
                context=context,
                parameters={"branch_name": event_branch, "kind": kind},
            )
        await self.repository.upsert(records=decision.to_record)

        return decision
