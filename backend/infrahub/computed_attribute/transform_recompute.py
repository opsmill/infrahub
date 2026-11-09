from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import InfrahubKind
from infrahub.core.registry import registry
from infrahub.log import get_logger
from infrahub.workflows.catalogue import TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES
from infrahub.workflows.constants import WorkflowTag

from .recompute_resolution import RecomputeResolver

if TYPE_CHECKING:
    from infrahub_sdk.node import InfrahubNode

    from infrahub.events.models import EventContext
    from infrahub.services.adapters.workflow import InfrahubWorkflow

log = get_logger()


class TransformFetcher(Protocol):
    """Fetches a Python transform node by id, returning ``None`` when it is gone."""

    async def get(self, *, kind: str, id: str, branch: str, raise_when_missing: bool) -> InfrahubNode | None: ...


class TransformRecomputeSubmitter:
    """Resolve a Python transform to the attributes it feeds and fan out their recompute.

    Holds no Prefect orchestration, so an injected fetcher and workflow make it testable.
    """

    def __init__(self, client: TransformFetcher, workflow: InfrahubWorkflow) -> None:
        self._client = client
        self._workflow = workflow

    async def submit(self, *, branch_name: str, transform_id: str, context: EventContext) -> int:
        """Fan out a recompute for every attribute the transform feeds; return the count submitted.

        A transform that no longer resolves (branch race, or an already-landed delete) returns 0.
        """
        transform = await self._client.get(
            kind=InfrahubKind.TRANSFORMPYTHON, id=transform_id, branch=branch_name, raise_when_missing=False
        )
        if transform is None:
            log.warning(f"Transform {transform_id} not found on {branch_name}; skipping recompute")
            return 0

        schema_branch = registry.schema.get_schema_branch(name=branch_name)
        resolver = RecomputeResolver(
            attributes_by_transform=schema_branch.computed_attributes.python_attributes_by_transform
        )
        definitions = resolver.resolve(transform_name=transform.name.value, transform_id=transform_id)

        log.info(
            f"Transform {transform.name.value} ({transform_id}) on {branch_name}: recomputing "
            f"{len(definitions)} computed attribute(s)"
        )
        for definition in definitions:
            await self._workflow.submit_workflow(
                workflow=TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
                context=context,
                parameters={
                    "branch_name": branch_name,
                    "computed_attribute_name": definition.attribute.name,
                    "computed_attribute_kind": definition.kind,
                    "context": context,
                },
                # Must be a creation tag: in-flow tag updates drop tags added mid-run.
                tags=[WorkflowTag.BRANCH.render(identifier=branch_name)],
            )
        return len(definitions)
