from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema_change.constants import SCHEMA_CHANGE_HISTORY_MAX_LIMIT, SCHEMA_CHANGE_OPERATIONS_MAX_LIMIT
from infrahub.core.schema_change.factory import build_schema_change_history_reader
from tests.helpers.schema import RACK_SCHEMA
from tests.helpers.schema.rack import CARD, SLOT
from tests.helpers.schema_change import ApplicationWithMigrations, read_applications_with_migrations
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.schema_change.history_reader import SchemaChangeHistoryPage, SchemaOperationPage
    from infrahub.database import InfrahubDatabase

SCHEMA_CHANGE_BRANCH = "schema-change-history"
SCHEMA_FILE_VERSION = "1.0"

RACK_KIND = "TestingRack"
SLOT_KIND = "TestingSlot"
POWER_SLOT_KIND = "TestingPowerSlot"
CARD_KIND = "TestingCard"

SERIAL_ATTRIBUTE = "serial"
SERIAL_LABEL = "Serial number"
POSITION_ATTRIBUTE = "position"
HEIGHT_ATTRIBUTE = "height"
SHARED_CARD_NAME = "line-card"
"""The name of both cards, so that making the name unique fails on the data."""

INVALID_HUMAN_FRIENDLY_ID = "name__value__serial__value"


@dataclass(frozen=True)
class SchemaChangeDataset:
    branch_name: str
    rack_id: str
    slot_ids: list[str]
    card_ids: list[str]


@dataclass(frozen=True)
class SchemaChangeHistorySnapshot:
    """Every record of the schema changes of one branch, read in pages large enough to hold them all.

    The entries of `page` are in the order the schema changes were created, the oldest first.
    """

    page: SchemaChangeHistoryPage
    operations: dict[str, SchemaOperationPage]
    applications: dict[str, list[ApplicationWithMigrations]]

    @property
    def schema_change_ids(self) -> list[str]:
        return [str(entry.schema_change.uuid) for entry in self.page.entries]


async def read_schema_change_history(db: InfrahubDatabase, branch: str) -> SchemaChangeHistorySnapshot:
    reader = build_schema_change_history_reader(db=db)
    newest_first = await reader.list_schema_changes(branch=branch, limit=SCHEMA_CHANGE_HISTORY_MAX_LIMIT, offset=0)
    page = replace(
        newest_first,
        entries=sorted(
            newest_first.entries, key=lambda entry: (entry.schema_change.created_at, str(entry.schema_change.uuid))
        ),
    )
    schema_change_ids = [str(entry.schema_change.uuid) for entry in page.entries]
    operations = await reader.list_operations(
        schema_change_ids=schema_change_ids, limit=SCHEMA_CHANGE_OPERATIONS_MAX_LIMIT, offset=0
    )
    applications = await read_applications_with_migrations(db=db, schema_change_ids=schema_change_ids)
    return SchemaChangeHistorySnapshot(page=page, operations=operations, applications=applications)


def _schema_file(schema_root: SchemaRoot) -> dict[str, Any]:
    schema_root.version = SCHEMA_FILE_VERSION
    return schema_root.model_dump(exclude_unset=True)


class TestSchemaChangeBase(TestInfrahubApp):
    """Loads the rack schema on main, creates two power slots with a card each in a rack, then creates a branch."""

    @pytest.fixture(scope="class")
    def schema_base(self) -> dict[str, Any]:
        return _schema_file(RACK_SCHEMA.duplicate())

    @pytest.fixture(scope="class")
    def schema_card_serial(self) -> dict[str, Any]:
        """Add an optional attribute to the card."""
        card = CARD.duplicate()
        card.attributes.append(AttributeSchema(name=SERIAL_ATTRIBUTE, kind="Text", optional=True))
        return _schema_file(SchemaRoot(nodes=[card]))

    @pytest.fixture(scope="class")
    def schema_card_serial_label(self) -> dict[str, Any]:
        """Change only the label of the attribute that the file before added."""
        card = CARD.duplicate()
        card.attributes.append(AttributeSchema(name=SERIAL_ATTRIBUTE, kind="Text", optional=True, label=SERIAL_LABEL))
        return _schema_file(SchemaRoot(nodes=[card]))

    @pytest.fixture(scope="class")
    def schema_card_unique_name(self) -> dict[str, Any]:
        """Make the name of the card unique, which the two cards of the data set share."""
        card = CARD.duplicate()
        card.get_attribute(name="name").unique = True
        card.attributes.append(AttributeSchema(name=SERIAL_ATTRIBUTE, kind="Text", optional=True, label=SERIAL_LABEL))
        return _schema_file(SchemaRoot(nodes=[card]))

    @pytest.fixture(scope="class")
    def schema_card_invalid_human_friendly_id(self) -> dict[str, Any]:
        card = CARD.duplicate()
        card.human_friendly_id = [INVALID_HUMAN_FRIENDLY_ID]
        card.attributes.append(AttributeSchema(name=SERIAL_ATTRIBUTE, kind="Text", optional=True, label=SERIAL_LABEL))
        return _schema_file(SchemaRoot(nodes=[card]))

    @pytest.fixture(scope="class")
    def schema_slot_position(self) -> dict[str, Any]:
        """Add an optional attribute to the generic that the power slot inherits."""
        slot = SLOT.duplicate()
        slot.attributes.append(AttributeSchema(name=POSITION_ATTRIBUTE, kind="Number", optional=True))
        return _schema_file(SchemaRoot(generics=[slot]))

    @pytest.fixture(scope="class")
    def schema_slot_height(self) -> dict[str, Any]:
        """Add a second optional attribute to the generic that the power slot inherits."""
        slot = SLOT.duplicate()
        slot.attributes.append(AttributeSchema(name=POSITION_ATTRIBUTE, kind="Number", optional=True))
        slot.attributes.append(AttributeSchema(name=HEIGHT_ATTRIBUTE, kind="Number", optional=True))
        return _schema_file(SchemaRoot(generics=[slot]))

    @pytest.fixture(scope="class")
    async def schema_change_dataset(
        self, initialize_registry: None, client: InfrahubClient, schema_base: dict[str, Any]
    ) -> SchemaChangeDataset:
        response = await client.schema.load(schemas=[schema_base])
        assert response.errors == {}

        cards = []
        for _ in range(2):
            card = await client.create(kind=CARD_KIND, name=SHARED_CARD_NAME)
            await card.save()
            cards.append(card)

        slots = []
        for position, card in enumerate(cards, start=1):
            slot = await client.create(kind=POWER_SLOT_KIND, name=f"slot-{position}", card=card)
            await slot.save()
            slots.append(slot)

        rack = await client.create(kind=RACK_KIND, name="rack-1", slots=slots)
        await rack.save()

        branch = await client.branch.create(branch_name=SCHEMA_CHANGE_BRANCH)

        return SchemaChangeDataset(
            branch_name=branch.name,
            rack_id=rack.id,
            slot_ids=[slot.id for slot in slots],
            card_ids=[card.id for card in cards],
        )
