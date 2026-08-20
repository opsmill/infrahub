from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.regeneration.models import RegenerationReason, RegenerationTrigger
from infrahub.core.regeneration.predicates import classify_untrusted_dependency_closure

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .models import DefinitionModel


def repositories_forcing_full_regeneration(*, definitions: Sequence[DefinitionModel]) -> dict[str, RegenerationTrigger]:
    """Map each repository that must regenerate every definition to the trigger that escalated it.

    A definition with no computed fingerprint has no trustworthy change signal, so its whole
    repository is regenerated rather than risk leaving a stale definition behind. The escalation
    self-heals once the repository is re-imported and its fingerprints are populated.
    """
    forced: dict[str, RegenerationTrigger] = {}
    for definition in definitions:
        if definition.fingerprint is not None or definition.repository_id in forced:
            continue
        forced[definition.repository_id] = RegenerationTrigger(
            code=RegenerationReason.MISSING_FINGERPRINT,
            detail=(
                f"repository {definition.repository_id} has a definition with no computed fingerprint; "
                f"regenerating every definition of the repository"
            ),
        )
    return forced


def dependency_closure_trigger(definition: DefinitionModel) -> RegenerationTrigger | None:
    """Return the trigger escalating a definition whose dependency closure cannot be trusted, or None.

    A missing or partial dependency closure means a code change outside the known inputs would
    not move the fingerprint, so the definition is regenerated defensively rather than narrowed.
    """
    code = classify_untrusted_dependency_closure(definition)
    if code is None:
        return None
    if code is RegenerationReason.DEPENDENCIES_NULL:
        detail = (
            f"{definition.definition_name}: {definition.source_noun} dependency closure is not computed "
            f"(dependencies=null); regenerating all {definition.instance_noun}"
        )
    else:
        detail = (
            f"{definition.definition_name}: {definition.source_noun} dependency closure is incomplete "
            f"(dependencies_complete={definition.dependencies_complete}); regenerating all {definition.instance_noun}"
        )
    return RegenerationTrigger(code=code, detail=detail)
