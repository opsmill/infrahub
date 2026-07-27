from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from infrahub.core.regeneration.members import map_subscriber_ids_by_member

from ..fallbacks import dependency_closure_trigger
from ..models import DefinitionModel

if TYPE_CHECKING:
    import logging

    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.regeneration.models import RegenerationTrigger

    from ..gate import DefinitionGate
    from ..impacted import ImpactedSubscriberResolver
    from ..models import LoadedDefinition


def _narrow_members_filter(rendered_members: list[str], total_members: int) -> list[str]:
    """Reduce the rendered members to the filter a regeneration request should carry.

    An empty filter means "every member", so only narrow to a strict subset that renders; when every
    member renders, the empty filter lets the whole group be resolved at execution time.
    """
    if len(rendered_members) == total_members:
        return []
    return rendered_members


class DefinitionSelectorBase[DefinitionT: DefinitionModel, RequestT](ABC):
    """Shared skeleton for narrowing a merge's regeneration to the definitions and members it touched.

    The template gates each definition, reconciles it against the members of its live target group,
    resolves which subscribers the diff actually impacted, and drops any definition whose members all
    fall away. Subclasses supply the kind-specific steps: loading the definitions with their group,
    fetching that group, deciding a single member's re-render, and building the run request.
    """

    subscriber_kind: str

    def __init__(
        self,
        client: InfrahubClient,
        gate: DefinitionGate,
        impacted_resolver: ImpactedSubscriberResolver,
        log: logging.Logger | logging.LoggerAdapter[logging.Logger],
    ) -> None:
        self.client = client
        self.gate = gate
        self.impacted_resolver = impacted_resolver
        self.log = log

    async def select(
        self,
        *,
        loaded_definitions: list[LoadedDefinition[DefinitionT]],
        forced_repositories: dict[str, RegenerationTrigger],
        diff_summary: list[NodeDiff],
        target_branch: str,
        modified_kinds: list[str],
    ) -> list[RequestT]:
        """Return one regeneration request per definition the merge diff requires be reprocessed.

        Each request is narrowed to the members whose inputs the diff actually changed; a definition
        left with no members to render produces no request. Every uncertain signal widens the
        selection rather than narrows it, so the result never omits a member the merge may have
        affected.
        """
        requests: list[RequestT] = []
        for loaded in loaded_definitions:
            definition = loaded.definition
            gate_result = self.gate.evaluate(
                definition=definition,
                diff_summary=diff_summary,
                modified_kinds=modified_kinds,
                group_id=loaded.group_id,
            )

            # A definition whose change signal cannot be trusted regenerates all of its members
            # rather than risk narrowing away one the merge affected.
            candidate_triggers = (
                forced_repositories.get(definition.repository_id),
                dependency_closure_trigger(definition),
            )
            forced_triggers = [trigger for trigger in candidate_triggers if trigger is not None]
            for trigger in forced_triggers:
                self.log.debug(trigger.detail)
            forced = bool(forced_triggers)

            if not (gate_result.selected or forced):
                continue
            regenerate_all_members = gate_result.regenerate_all_members or forced

            subscriber_by_member = await self._map_subscribers_by_member(
                definition=definition, target_branch=target_branch
            )
            member_ids = await self._fetch_member_ids(definition=definition, target_branch=target_branch)
            selection = await self.impacted_resolver.resolve(
                query_payload=definition.query_payload,
                diff_summary=diff_summary,
                target_branch=target_branch,
                subscriber_kind=self.subscriber_kind,
                every_target=list(subscriber_by_member.values()),
            )
            impacted = selection.ids

            rendered_members = [
                member_id
                for member_id in member_ids
                if self._should_render(
                    subscriber_id=subscriber_by_member.get(member_id),
                    regenerate_all_members=regenerate_all_members,
                    impacted=impacted,
                )
            ]
            self.log.debug(
                f"SELECTIVE_REGEN select [{definition.definition_name}]: "
                f"regenerate_all_members={regenerate_all_members} forced={forced} "
                f"members={len(member_ids)} mapped_subscribers={len(subscriber_by_member)} "
                f"impacted={len(impacted)} rendered={len(rendered_members)}"
            )
            if not rendered_members:
                continue
            members = _narrow_members_filter(rendered_members, len(member_ids))
            requests.append(self._build_request(definition=definition, target_branch=target_branch, members=members))
        return requests

    async def _map_subscribers_by_member(self, *, definition: DefinitionT, target_branch: str) -> dict[str, str]:
        """Map each member to the id of its existing subscriber for this definition on the branch.

        A member with no resolvable existing subscriber is absent from the map, so it is treated as
        new and always regenerated; orphan records whose target no longer resolves are skipped. The
        map lets each member's re-render be decided without a further per-member lookup.
        """
        existing = await self.client.filters(
            kind=self.subscriber_kind,
            definition__ids=[definition.definition_id],
            include=["object"],
            branch=target_branch,
        )
        return map_subscriber_ids_by_member(
            existing_subscribers=existing, definition_name=definition.definition_name, log=self.log
        )

    @abstractmethod
    async def load_definitions(self, *, target_branch: str) -> list[LoadedDefinition[DefinitionT]]:
        """Load the candidate definitions for this kind, each paired with its target group id."""

    @abstractmethod
    async def _fetch_member_ids(self, *, definition: DefinitionT, target_branch: str) -> list[str]:
        """Return the ids of the members of the definition's live target group on the merge target branch."""

    @abstractmethod
    def _should_render(self, *, subscriber_id: str | None, regenerate_all_members: bool, impacted: list[str]) -> bool:
        """Whether a single member's subscriber must be regenerated."""

    @abstractmethod
    def _build_request(self, *, definition: DefinitionT, target_branch: str, members: list[str]) -> RequestT:
        """Build the regeneration request dispatched for a selected definition."""
