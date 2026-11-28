from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.events.schemas.automations import EventTrigger

from infrahub.core.template_fingerprint.models import FingerprintKey, RecordedFingerprint, TemplateFamily
from infrahub.log import get_logger
from infrahub.trigger.constants import NAME_SEPARATOR, TRIGGER_PLACEHOLDER_FIELD

if TYPE_CHECKING:
    from collections.abc import Sequence

    from prefect.events.schemas.automations import Automation

    from infrahub.core.template_fingerprint.models import SchemaFingerprints
    from infrahub.core.template_fingerprint.repository import TemplateFingerprintRepository

FIELD_NAME_LABEL = "infrahub.field.name"
HASH_MARKER = "| hash:"
BY_SEGMENT = "by"
# <branch>, <kind>, "by", <kind>: the branch name may itself contain the separator, so split from the right.
NAME_SEGMENT_SPLITS = 3


def _matched_fields(automation: Automation) -> set[str]:
    trigger = automation.trigger
    if not isinstance(trigger, EventTrigger):
        return set()
    specifications = trigger.match_related if isinstance(trigger.match_related, list) else [trigger.match_related]
    fields: set[str] = set()
    for specification in specifications:
        value = specification.get(FIELD_NAME_LABEL)
        if isinstance(value, str):
            fields.add(value)
        elif isinstance(value, list):
            fields.update(value)
    return fields


def _family_of(name: str) -> TemplateFamily | None:
    for family in TemplateFamily:
        if name.startswith(f"{family.value}{NAME_SEPARATOR}"):
            return family
    return None


def parse_placeholder_automation(
    automation: Automation, schemas: Sequence[SchemaFingerprints]
) -> RecordedFingerprint | None:
    """Return the fingerprint held by a display label or HFID placeholder automation, or None when it is not one."""
    family = _family_of(automation.name)
    if family is None:
        return None

    if _matched_fields(automation) != {TRIGGER_PLACEHOLDER_FIELD}:
        return None

    branch_and_kind = _branch_and_kind(name=automation.name, family=family)
    fingerprint = _fingerprint(description=automation.description)
    if branch_and_kind is None or fingerprint is None:
        return None

    branch, kind = branch_and_kind
    in_scope = {branch_name for schema in schemas if schema.family == family for branch_name in schema.by_branch}
    if branch not in in_scope:
        return None

    return RecordedFingerprint(key=FingerprintKey(family=family, branch=branch, kind=kind), fingerprint=fingerprint)


def _branch_and_kind(name: str, family: TemplateFamily) -> tuple[str, str] | None:
    segments = name.removeprefix(f"{family.value}{NAME_SEPARATOR}").rsplit(NAME_SEPARATOR, NAME_SEGMENT_SPLITS)
    if len(segments) != NAME_SEGMENT_SPLITS + 1:
        return None
    branch, target_kind, by_segment, node_kind = segments
    if not branch or by_segment != BY_SEGMENT or target_kind != node_kind:
        return None
    return branch, node_kind


def _fingerprint(description: str) -> str | None:
    _, marker, fingerprint = description.rpartition(HASH_MARKER)
    fingerprint = fingerprint.strip()
    if not marker or not fingerprint:
        return None
    return fingerprint


async def carry_over_placeholder_fingerprints(
    deleted: Sequence[Automation],
    schemas: Sequence[SchemaFingerprints],
    repository: TemplateFingerprintRepository,
) -> int:
    """Record the fingerprints of deleted placeholder automations that have no record yet; return the number created."""
    log = get_logger()
    records: list[RecordedFingerprint] = []
    for automation in deleted:
        record = parse_placeholder_automation(automation=automation, schemas=schemas)
        if record is None:
            log.debug(f"Automation {automation.name} is not a placeholder to carry over")
            continue
        records.append(record)

    return await repository.insert_missing(records=records)
