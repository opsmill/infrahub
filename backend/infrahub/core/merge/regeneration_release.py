"""Release the regeneration held for a repository once its pending merges left the queue, delivered or abandoned."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, assert_never

from infrahub_sdk.protocols import CoreGeneratorDefinition, CoreTransformPython

from infrahub.computed_attribute.recompute_resolution import RecomputeResolver
from infrahub.core.constants import FullRegenerationReason
from infrahub.exceptions import ServiceUnavailableError
from infrahub.log import get_logger

from .python_target_sources import DeclaredAttribute
from .recompute_coalescing import CoalescedRecompute, PythonTargetRequest, whole_kind_python_target

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Collection, Iterable

    from infrahub_sdk.client import InfrahubClient
    from pydantic import BaseModel

    from infrahub.context import InfrahubContext
    from infrahub.core.schema.manager import SchemaManager
    from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
    from infrahub.git.models import RequestArtifactDefinitionGenerate
    from infrahub.git.writeback.models import HeldItem, HeldPythonAttribute, HeldRegeneration
    from infrahub.message_bus.types import ProposedChangeArtifactDefinition

    from .recompute_coalescing import AffectedTarget, CoalescedRecomputeSubmitter
    from .regeneration_barrier import NarrowedHoldCache
    from .regeneration_dispatcher import PostMergeRegenerationDispatcher
    from .selective_regen.definition_selector.base import DefinitionSelectorBase
    from .selective_regen.models import DefinitionModel

log = get_logger()


class HeldDefinitionSource(Protocol):
    """The held definitions as they are now, and the Python computed attributes that a repository owns."""

    async def artifact_requests(
        self, *, branch: str, ids: Collection[str]
    ) -> dict[str, RequestArtifactDefinitionGenerate]:
        """Return the request with no member narrowing of each artifact definition that exists, by its id."""

    async def generator_requests(
        self, *, branch: str, ids: Collection[str]
    ) -> dict[str, RequestGeneratorDefinitionRun | None]:
        """Return the request with no target narrowing of each generator definition that exists, by its id.

        A definition that exists but does not run after a merge maps to None.
        """

    async def python_attributes(self, *, branch: str, repository_id: str) -> list[DeclaredAttribute]:
        """Return the Python computed attributes whose transform the repository owns."""


class HeldDefinitionResolver:
    """Load the held definitions with the queries and the request builders of the merge selectors."""

    def __init__(
        self,
        artifact_selector: DefinitionSelectorBase[ProposedChangeArtifactDefinition, RequestArtifactDefinitionGenerate],
        generator_selector: DefinitionSelectorBase[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun],
        client: InfrahubClient,
        schema_manager: SchemaManager,
    ) -> None:
        self.artifact_selector = artifact_selector
        self.generator_selector = generator_selector
        self.client = client
        self.schema_manager = schema_manager

    async def artifact_requests(
        self, *, branch: str, ids: Collection[str]
    ) -> dict[str, RequestArtifactDefinitionGenerate]:
        return await self._unnarrowed_requests(selector=self.artifact_selector, branch=branch, ids=ids)

    async def generator_requests(
        self, *, branch: str, ids: Collection[str]
    ) -> dict[str, RequestGeneratorDefinitionRun | None]:
        runs = await self._unnarrowed_requests(selector=self.generator_selector, branch=branch, ids=ids)
        requests: dict[str, RequestGeneratorDefinitionRun | None] = dict(runs)
        missing = [definition_id for definition_id in ids if definition_id not in requests]
        if missing:
            # The selector loads only the definitions that run after a merge, so a missing one can still exist.
            existing = await self.client.filters(kind=CoreGeneratorDefinition, ids=missing, branch=branch)
            requests.update(dict.fromkeys((generator.id for generator in existing), None))
        return requests

    async def python_attributes(self, *, branch: str, repository_id: str) -> list[DeclaredAttribute]:
        transforms = await self.client.filters(kind=CoreTransformPython, branch=branch, repository__ids=[repository_id])
        attributes = RecomputeResolver.from_schema_branch(self.schema_manager.get_schema_branch(name=branch))
        return [
            DeclaredAttribute(kind=definition.kind, attribute_name=definition.attribute.name)
            for transform in transforms
            for definition in attributes.resolve(transform_name=transform.name.value, transform_id=transform.id)
        ]

    async def _unnarrowed_requests[DefinitionT: DefinitionModel, RequestT](
        self, *, selector: DefinitionSelectorBase[DefinitionT, RequestT], branch: str, ids: Collection[str]
    ) -> dict[str, RequestT]:
        if not ids:
            return {}
        return {
            loaded.definition.definition_id: selector.unnarrowed_request(
                definition=loaded.definition, target_branch=branch
            )
            for loaded in await selector.load_definitions(target_branch=branch)
            if loaded.definition.definition_id in ids
        }


class HeldRegenerationReleaser:
    """Dispatch the regeneration held for a repository, once its merges left the queue, delivered or abandoned.

    A held item takes its narrowing from the request kept at its hold, and every other field from its
    definition as it is now, because the delivery's import can change the definition after the hold.
    """

    def __init__(
        self,
        dispatcher: PostMergeRegenerationDispatcher,
        python_submitter: CoalescedRecomputeSubmitter,
        definitions: HeldDefinitionSource,
        narrowed: NarrowedHoldCache,
        default_branch_name: str,
        context: InfrahubContext,
    ) -> None:
        self.dispatcher = dispatcher
        self.python_submitter = python_submitter
        self.definitions = definitions
        self.narrowed = narrowed
        self.default_branch_name = default_branch_name
        self.context = context

    async def release(
        self, *, repository_id: str, held: HeldRegeneration, renew: Callable[[], Awaitable[None]]
    ) -> None:
        """Dispatch the items of the window, and call `renew` after each awaited step.

        It changes no delivery state of the released repository, so after a failed dispatch every item of the
        window stays held. Its dispatches pass the barrier, which can hold work of other pending repositories.

        Raises:
            ServiceUnavailableError: The submission of a Python recompute was skipped.
            Exception: Any error of a submission, a dispatch or a definition read propagates.

        """
        terminals_reason: FullRegenerationReason | None = None
        if held.widen is not None:
            match held.widen.scope:
                case "all":
                    await self._release_repository(
                        repository_id=repository_id, held=held, reason=held.widen.reason, renew=renew
                    )
                    return
                case "terminals":
                    terminals_reason = held.widen.reason
                case _:
                    assert_never(held.widen.scope)

        artifacts = await self.definitions.artifact_requests(
            branch=self.default_branch_name, ids=[item.id for item in held.artifact_definitions]
        )
        generators = await self.definitions.generator_requests(
            branch=self.default_branch_name, ids=[item.id for item in held.generator_definitions]
        )
        await renew()
        unresolved = sorted(
            ({item.id for item in held.artifact_definitions} - artifacts.keys())
            | ({item.id for item in held.generator_definitions} - generators.keys())
        )
        if unresolved:
            await self._release_repository(
                repository_id=repository_id,
                held=held,
                reason=FullRegenerationReason.HELD_SET_UNRESOLVED,
                renew=renew,
                unresolved_ids=unresolved,
            )
            return

        not_run = sorted(definition_id for definition_id, request in generators.items() if request is None)
        if not_run:
            log.info(
                "The held generator definitions no longer run after a merge, so the release runs nothing for them",
                repository_id=repository_id,
                generator_definition_ids=not_run,
            )
        generator_runs = [
            await self._narrowed_request(
                repository_id=repository_id, item=item, unnarrowed=request, narrowing={"target_members"}
            )
            for item in held.generator_definitions
            if (request := generators[item.id]) is not None
        ]
        artifact_generates: list[RequestArtifactDefinitionGenerate] = []
        if terminals_reason is not None:
            log.info(
                "Regenerating every artifact definition of the repository to release its held regeneration",
                repository_id=repository_id,
                reason=terminals_reason,
            )
            await self.dispatcher.submit_repository_regeneration(
                context=self.context,
                target_branch=self.default_branch_name,
                repository_id=repository_id,
                scope="terminals",
            )
            await renew()
        else:
            artifact_generates = [
                await self._narrowed_request(
                    repository_id=repository_id,
                    item=item,
                    unnarrowed=artifacts[item.id],
                    narrowing={"members", "limit"},
                )
                for item in held.artifact_definitions
            ]

        if generator_runs or artifact_generates:
            # The narrowed requests were read from the cache since the last renewal.
            await renew()
            await self.dispatcher.dispatch_requests(
                context=self.context,
                target_branch=self.default_branch_name,
                generator_runs=generator_runs,
                artifact_generates=artifact_generates,
                releasing=repository_id,
                renew=renew,
            )

        await self._recompute(
            targets=[
                await self._held_python_target(repository_id=repository_id, item=item)
                for item in held.python_attributes
            ],
            renew=renew,
        )

    async def _release_repository(
        self,
        *,
        repository_id: str,
        held: HeldRegeneration,
        reason: FullRegenerationReason,
        renew: Callable[[], Awaitable[None]],
        **log_context: object,
    ) -> None:
        log.info(
            "Regenerating every definition of the repository to release its held regeneration",
            repository_id=repository_id,
            reason=reason,
            **log_context,
        )
        await self.dispatcher.submit_repository_regeneration(
            context=self.context, target_branch=self.default_branch_name, repository_id=repository_id, scope="all"
        )
        await renew()
        owned = await self.definitions.python_attributes(branch=self.default_branch_name, repository_id=repository_id)
        await renew()
        # A held attribute whose owner was unknown at its hold is not in the owned list.
        await self._recompute(
            targets=[
                *(whole_kind_python_target(kind=item.kind, attribute_name=item.attribute_name) for item in owned),
                *(
                    whole_kind_python_target(kind=item.kind, attribute_name=item.attribute)
                    for item in held.python_attributes
                ),
            ],
            renew=renew,
        )

    async def _narrowed_request[RequestT: BaseModel](
        self, *, repository_id: str, item: HeldItem, unnarrowed: RequestT, narrowing: set[str]
    ) -> RequestT:
        """Copy the `narrowing` fields of the request kept at the hold onto the request built now."""
        kept = await self.narrowed.get(
            repository_id=repository_id, hold_seq=item.hold_seq, identifier=item.identifier, model=type(unnarrowed)
        )
        if kept is None:
            return unnarrowed
        return unnarrowed.model_copy(update=kept.model_dump(include=narrowing))

    async def _held_python_target(self, *, repository_id: str, item: HeldPythonAttribute) -> AffectedTarget:
        """Return the target kept at the hold, or the whole kind when the cache misses."""
        kept = await self.narrowed.get(
            repository_id=repository_id, hold_seq=item.hold_seq, identifier=item.identifier, model=PythonTargetRequest
        )
        if kept is None:
            return whole_kind_python_target(kind=item.kind, attribute_name=item.attribute)
        return kept.target

    async def _recompute(self, *, targets: Iterable[AffectedTarget], renew: Callable[[], Awaitable[None]]) -> None:
        coalesced = CoalescedRecompute(branch=self.default_branch_name, targets=frozenset(targets))
        if not coalesced.targets:
            return
        planned = self.python_submitter.plan(coalesced)
        submitted = await self.python_submitter.submit(coalesced=coalesced, context=self.context.to_event_context())
        # A failed submission is only logged and skipped, so without this check the held attribute is never recomputed.
        skipped = [submission for submission in planned if submission not in submitted]
        if skipped:
            names = ", ".join(f"{submission.target_kind}.{submission.attribute_name}" for submission in skipped)
            raise ServiceUnavailableError(
                message=f"The recompute of the Python computed attributes {names} could not be submitted."
            )
        await renew()
