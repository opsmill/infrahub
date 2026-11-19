from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import pytest
from prefect.events.schemas.automations import Automation, EventTrigger, Posture
from prefect.events.schemas.events import ResourceSpecification

from infrahub.core.template_fingerprint.models import (
    FingerprintKey,
    RecordedFingerprint,
    SchemaFingerprints,
    TemplateFamily,
)
from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD
from infrahub.trigger.placeholder_carry_over import parse_placeholder_automation

DESCRIPTION = "Automation for Trigger TestCar::by::TestCar of type display_label_jinja2 (v1.12.0) | hash:abc123"

SCHEMAS = [
    SchemaFingerprints(
        family=TemplateFamily.DISPLAY_LABEL_JINJA2,
        by_branch={"main": {}, "feature/a-b": {}},
    ),
    SchemaFingerprints(family=TemplateFamily.HUMAN_FRIENDLY_ID, by_branch={"main": {}}),
]


def _automation(name: str, fields: list[str], description: str) -> Automation:
    match_related: list[ResourceSpecification] = [
        ResourceSpecification(
            {
                "prefect.resource.role": ["infrahub.node.attribute_update", "infrahub.node.relationship_update"],
                "infrahub.field.name": fields,
            }
        ),
        ResourceSpecification({"prefect.resource.role": "infrahub.branch", "infrahub.resource.label": "!other"}),
    ]
    return Automation(
        id=uuid4(),
        name=name,
        description=description,
        enabled=True,
        trigger=EventTrigger(
            expect={"infrahub.node.updated"},
            match=ResourceSpecification({"infrahub.node.kind": "TestCar"}),
            match_related=match_related,
            posture=Posture.Reactive,
        ),
        actions=[],
    )


@dataclass
class ParseCase:
    name: str
    automation_name: str
    expected: RecordedFingerprint | None
    fields: list[str] = field(default_factory=lambda: [TRIGGER_PLACEHOLDER_FIELD])
    description: str = DESCRIPTION


PARSE_CASES = [
    ParseCase(
        name="other-family-prefix",
        automation_name="computed_attr_jinja2::main::TestCar::by::TestCar",
        expected=None,
    ),
    ParseCase(
        name="family-prefix-without-separator",
        automation_name="display_label_jinja2_extra::main::TestCar::by::TestCar",
        expected=None,
    ),
    ParseCase(
        name="trigger-on-real-fields",
        automation_name="display_label_jinja2::main::TestCar::by::TestCar",
        fields=["color", "name"],
        expected=None,
    ),
    ParseCase(
        name="trigger-on-placeholder-and-real-field",
        automation_name="display_label_jinja2::main::TestCar::by::TestCar",
        fields=[TRIGGER_PLACEHOLDER_FIELD, "name"],
        expected=None,
    ),
    ParseCase(
        name="branch-name-with-slash-and-dash",
        automation_name="display_label_jinja2::feature/a-b::TestCar::by::TestCar",
        expected=RecordedFingerprint(
            key=FingerprintKey(family=TemplateFamily.DISPLAY_LABEL_JINJA2, branch="feature/a-b", kind="TestCar"),
            fingerprint="abc123",
        ),
    ),
    ParseCase(
        name="different-kinds-around-by",
        automation_name="display_label_jinja2::main::TestCar::by::TestPerson",
        expected=None,
    ),
    ParseCase(
        name="no-by-segment",
        automation_name="display_label_jinja2::main::TestCar::from::TestCar",
        expected=None,
    ),
    ParseCase(
        name="no-branch-segment",
        automation_name="display_label_jinja2::TestCar::by::TestCar",
        expected=None,
    ),
    ParseCase(
        name="description-without-hash",
        automation_name="display_label_jinja2::main::TestCar::by::TestCar",
        description="Automation for Trigger TestCar::by::TestCar (v1.12.0)",
        expected=None,
    ),
    ParseCase(
        name="description-with-empty-hash",
        automation_name="display_label_jinja2::main::TestCar::by::TestCar",
        description="Automation for Trigger TestCar::by::TestCar (v1.12.0) | hash:",
        expected=None,
    ),
    ParseCase(
        name="branch-not-in-scope",
        automation_name="display_label_jinja2::deleted-branch::TestCar::by::TestCar",
        expected=None,
    ),
    ParseCase(
        name="branch-in-scope-of-the-other-family-only",
        automation_name="human_friendly_id::feature/a-b::TestCar::by::TestCar",
        expected=None,
    ),
    ParseCase(
        name="display-label-placeholder",
        automation_name="display_label_jinja2::main::TestCar::by::TestCar",
        expected=RecordedFingerprint(
            key=FingerprintKey(family=TemplateFamily.DISPLAY_LABEL_JINJA2, branch="main", kind="TestCar"),
            fingerprint="abc123",
        ),
    ),
    ParseCase(
        name="hfid-placeholder",
        automation_name="human_friendly_id::main::TestCar::by::TestCar",
        expected=RecordedFingerprint(
            key=FingerprintKey(family=TemplateFamily.HUMAN_FRIENDLY_ID, branch="main", kind="TestCar"),
            fingerprint="abc123",
        ),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in PARSE_CASES])
def test_parse_placeholder_automation(case: ParseCase) -> None:
    automation = _automation(name=case.automation_name, fields=case.fields, description=case.description)

    assert parse_placeholder_automation(automation=automation, schemas=SCHEMAS) == case.expected
