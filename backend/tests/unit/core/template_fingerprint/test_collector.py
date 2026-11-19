from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.models import SchemaBranchHash
from infrahub.core.registry import registry
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema.schema_branch_display import DisplayLabels, TemplateLabel
from infrahub.core.schema.schema_branch_display import RelationshipIdentifier as LabelRelationshipIdentifier
from infrahub.core.schema.schema_branch_display import RelationshipTriggers as LabelRelationshipTriggers
from infrahub.core.schema.schema_branch_hfid import HFIDDefinition, HFIDs
from infrahub.core.schema.schema_branch_hfid import RelationshipIdentifier as HFIDRelationshipIdentifier
from infrahub.core.schema.schema_branch_hfid import RelationshipTriggers as HFIDRelationshipTriggers
from infrahub.core.template_fingerprint.collector import (
    collect_schema_fingerprints,
    fingerprints_from_schema_branches,
)
from infrahub.core.template_fingerprint.models import SchemaFingerprints, TemplateFamily
from infrahub.display_labels.models import DisplayLabelTriggerDefinition
from infrahub.hfid.models import HFIDTriggerDefinition
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import TriggerType

if TYPE_CHECKING:
    from collections.abc import Mapping

CAR_LABEL = "{{ name__value }} {{ owner__name__value }}"
PERSON_LABEL = "{{ name__value }}"
CAR_HFID = ["name__value", "owner__name__value"]
PERSON_HFID = ["name__value"]

# Pinned so that a change of the hashing, which would trigger a full recompute after an upgrade, breaks the test.
CAR_LABEL_HASH = "a2696446d5f2f9d5acea3d72bde0bfbe"
PERSON_LABEL_HASH = "74576abd51e4daecda5aada7d4050835"
CAR_HFID_HASH = "42959de8acc8b6417a6486e286492eec"
PERSON_HFID_HASH = "9e3cf3278510d5197f64cabcd4b126ac"


def _schema_branch(name: str, car_label: str = CAR_LABEL, car_hfid: list[str] | None = None) -> SchemaBranch:
    hfid = car_hfid or CAR_HFID
    display_labels = DisplayLabels(
        template_based_display_labels={
            "TestCar": TemplateLabel(template=car_label, attributes={"name"}, relationships={"owner"}),
            "TestPerson": TemplateLabel(template=PERSON_LABEL, attributes={"name"}),
        },
        template_relationship_triggers={
            "TestPerson": LabelRelationshipTriggers(
                attributes={
                    "name": {LabelRelationshipIdentifier(kind="TestCar", filter_key="owner__ids", template=car_label)}
                }
            )
        },
    )
    hfids = HFIDs(
        node_level_hfids={
            "TestCar": HFIDDefinition(hfid=hfid, attributes={"name"}, relationships={"owner"}),
            "TestPerson": HFIDDefinition(hfid=PERSON_HFID, attributes={"name"}),
        },
        relationship_triggers={
            "TestPerson": HFIDRelationshipTriggers(
                attributes={"name": {HFIDRelationshipIdentifier(kind="TestCar", hfid=hfid, filter_key="owner__ids")}}
            )
        },
    )
    return SchemaBranch(cache={}, name=name, display_labels=display_labels, hfids=hfids)


def test_families_match_the_trigger_types_of_the_automations() -> None:
    assert TemplateFamily.DISPLAY_LABEL_JINJA2.value == TriggerType.DISPLAY_LABEL_JINJA2.value
    assert TemplateFamily.HUMAN_FRIENDLY_ID.value == TriggerType.HUMAN_FRIENDLY_ID.value


def test_display_label_fingerprints_are_the_template_hashes() -> None:
    fingerprints = fingerprints_from_schema_branches(
        family=TemplateFamily.DISPLAY_LABEL_JINJA2,
        schema_branches={"main": _schema_branch("main"), "b1": _schema_branch("b1", car_label="{{ name__value }}")},
    )

    assert fingerprints == SchemaFingerprints(
        family=TemplateFamily.DISPLAY_LABEL_JINJA2,
        by_branch={
            "main": {"TestCar": CAR_LABEL_HASH, "TestPerson": PERSON_LABEL_HASH},
            "b1": {"TestCar": PERSON_LABEL_HASH, "TestPerson": PERSON_LABEL_HASH},
        },
    )


def test_hfid_fingerprints_are_the_hfid_hashes() -> None:
    fingerprints = fingerprints_from_schema_branches(
        family=TemplateFamily.HUMAN_FRIENDLY_ID,
        schema_branches={"main": _schema_branch("main")},
    )

    assert fingerprints == SchemaFingerprints(
        family=TemplateFamily.HUMAN_FRIENDLY_ID,
        by_branch={"main": {"TestCar": CAR_HFID_HASH, "TestPerson": PERSON_HFID_HASH}},
    )


def _target_hashes(definitions: list[DisplayLabelTriggerDefinition] | list[HFIDTriggerDefinition]) -> dict[str, str]:
    """Map the kind each automation refreshes, the first part of its name, to the hash in its description."""
    hashes: dict[str, str] = {}
    for definition in definitions:
        target_kind = definition.name.split(NAME_SEPARATOR)[0]
        if isinstance(definition, DisplayLabelTriggerDefinition):
            hashes[target_kind] = definition.template_hash
        else:
            hashes[target_kind] = definition.hfid_hash
    return hashes


def test_fingerprints_equal_the_hashes_in_the_automations() -> None:
    schema_branch = _schema_branch("main")
    branches: Mapping[str, SchemaBranch] = {"main": schema_branch}

    label_hashes = _target_hashes(
        DisplayLabelTriggerDefinition.from_schema_display_labels(
            branch="main", display_labels=schema_branch.display_labels
        )
    )
    hfid_hashes = _target_hashes(HFIDTriggerDefinition.from_schema_hfids(branch="main", hfids=schema_branch.hfids))

    label_fingerprints = fingerprints_from_schema_branches(TemplateFamily.DISPLAY_LABEL_JINJA2, branches).by_branch
    hfid_fingerprints = fingerprints_from_schema_branches(TemplateFamily.HUMAN_FRIENDLY_ID, branches).by_branch

    # The peer automation of TestPerson carries the hash of the TestCar template it refreshes.
    assert label_hashes["TestCar"] == label_fingerprints["main"]["TestCar"] == CAR_LABEL_HASH
    assert hfid_hashes["TestCar"] == hfid_fingerprints["main"]["TestCar"] == CAR_HFID_HASH
    assert {kind: label_fingerprints["main"][kind] for kind in label_hashes} == label_hashes
    assert {kind: hfid_fingerprints["main"][kind] for kind in hfid_hashes} == hfid_hashes


@pytest.fixture
def registry_with_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    schema_manager = SchemaManager()
    for name, car_label in [("main", CAR_LABEL), ("same", CAR_LABEL), ("altered", PERSON_LABEL)]:
        schema_manager.set_schema_branch(name=name, schema=_schema_branch(name, car_label=car_label))

    monkeypatch.setattr(registry, "_schema", schema_manager)
    monkeypatch.setattr(
        registry,
        "branch",
        {
            "main": Branch(name="main", is_default=True, schema_hash=SchemaBranchHash(main="hash-main")),
            GLOBAL_BRANCH_NAME: Branch(name=GLOBAL_BRANCH_NAME, schema_hash=SchemaBranchHash(main="hash-global")),
            "same": Branch(name="same", schema_hash=SchemaBranchHash(main="hash-main")),
            "altered": Branch(name="altered", schema_hash=SchemaBranchHash(main="hash-altered")),
        },
    )


@pytest.mark.usefixtures("registry_with_branches")
def test_collect_reads_default_branch_and_altered_branches() -> None:
    fingerprints = collect_schema_fingerprints(TemplateFamily.DISPLAY_LABEL_JINJA2)

    assert fingerprints == SchemaFingerprints(
        family=TemplateFamily.DISPLAY_LABEL_JINJA2,
        by_branch={
            "main": {"TestCar": CAR_LABEL_HASH, "TestPerson": PERSON_LABEL_HASH},
            "altered": {"TestCar": PERSON_LABEL_HASH, "TestPerson": PERSON_LABEL_HASH},
        },
    )


@pytest.mark.usefixtures("registry_with_branches")
def test_collect_hfid_reads_default_branch_and_altered_branches() -> None:
    fingerprints = collect_schema_fingerprints(TemplateFamily.HUMAN_FRIENDLY_ID)

    assert fingerprints == SchemaFingerprints(
        family=TemplateFamily.HUMAN_FRIENDLY_ID,
        by_branch={
            "main": {"TestCar": CAR_HFID_HASH, "TestPerson": PERSON_HFID_HASH},
            "altered": {"TestCar": CAR_HFID_HASH, "TestPerson": PERSON_HFID_HASH},
        },
    )
