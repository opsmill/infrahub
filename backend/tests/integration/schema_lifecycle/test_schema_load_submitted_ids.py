"""Schema loads whose elements carry IDs, checked against the IDs the branch holds and the IDs ever stored.

Held IDs: a load keeps an ID the branch holds for the same element (an attribute rename) and refuses an ID the branch
holds for another element. Unknown IDs: a load ignores an ID that no schema element holds, refuses an ID of a deleted
element or of an element on another branch, and skips an absent element with such an ID.

The tests share one schema and data load and run in order: the later tests build on the state the earlier ones leave.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.schema import SchemaWarning, SchemaWarningKind, SchemaWarningType

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.schema.submitted_ids.resolver import IGNORED_ID_WARNING, SKIPPED_ABSENT_WARNING
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase

NAMESPACE = "Fieldid"
WIDGET_KIND = f"{NAMESPACE}Widget"
OTHER_KIND = f"{NAMESPACE}Other"
BRANCH_NAME = "ids-branch"

SERIAL = {"name": "serial_a", "kind": "Text", "optional": True}
MODEL = {"name": "model_a", "kind": "Text", "optional": True}
OLD = {"name": "old_a", "kind": "Text", "optional": True}
TAGS = {"name": "tags_r", "peer": "BuiltinTag", "cardinality": "many", "optional": True}


def _node(
    name: str,
    attributes: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "name": name,
        "namespace": NAMESPACE,
        "attributes": [{"name": "name", "kind": "Text", "unique": True}, *attributes],
        "relationships": relationships or [],
    }
    if node_id is not None:
        node["id"] = node_id
    return node


def _schema(*nodes: dict[str, Any]) -> dict[str, Any]:
    return {"version": "1.0", "nodes": list(nodes)}


def _error_body(message: str) -> dict[str, Any]:
    return {"data": None, "errors": [{"message": message, "extensions": {"code": 422}}]}


def _warning(message: str, kind: str, field: str | None) -> SchemaWarning:
    return SchemaWarning(
        type=SchemaWarningType.DEPRECATION,
        kinds=[SchemaWarningKind(kind=kind, field=field)],
        message=message,
    )


async def _vertex_ids(db: InfrahubDatabase, schema_kind: str, field_name: str) -> list[str]:
    rows = await NodeManager.query(db=db, schema=schema_kind, filters={"name__value": field_name})
    return sorted(row.id for row in rows)


def _main_hash() -> str:
    return registry.schema.get_schema_branch(name="main").get_hash()


@dataclass(frozen=True)
class StoredIds:
    widget_node: str
    serial: str
    model: str
    old: str
    tags: str
    widget_data: str
    tag_data: str


class TestSchemaLoadSubmittedIds(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def stored(self, client: InfrahubClient, initialize_registry: None) -> StoredIds:
        response = await client.schema.load(
            schemas=[_schema(_node("Widget", [SERIAL, MODEL, OLD], [TAGS]), _node("Other", []))]
        )
        assert not response.errors

        tag = await client.create(kind="BuiltinTag", name="t1")
        await tag.save()
        widget = await client.create(kind=WIDGET_KIND, name="w1", serial_a="ABC", model_a="X1", tags_r=[tag])
        await widget.save()

        widget_schema = registry.schema.get(name=WIDGET_KIND)
        return StoredIds(
            widget_node=widget_schema.get_id(),
            serial=widget_schema.get_attribute("serial_a").get_id(),
            model=widget_schema.get_attribute("model_a").get_id(),
            old=widget_schema.get_attribute("old_a").get_id(),
            tags=widget_schema.get_relationship("tags_r").get_id(),
            widget_data=widget.id,
            tag_data=tag.id,
        )

    async def test_check_reports_the_ignored_id_warning(self, client: InfrahubClient, stored: StoredIds) -> None:
        is_valid, body = await client.schema.check(
            schemas=[_schema(_node("Widget", [{**SERIAL, "id": str(uuid.uuid4())}]))]
        )

        assert is_valid is True
        assert body["warnings"] == [
            {
                "type": "deprecation",
                "kinds": [{"kind": WIDGET_KIND, "field": "serial_a"}],
                "message": IGNORED_ID_WARNING,
            }
        ]

    async def test_check_reports_the_same_error(self, client: InfrahubClient, stored: StoredIds) -> None:
        is_valid, body = await client.schema.check(
            schemas=[_schema(_node("Other", [{**SERIAL, "name": "check_stolen_a", "id": stored.serial}]))]
        )

        assert is_valid is False
        assert body == _error_body(
            f"{OTHER_KIND}.check_stolen_a: id '{stored.serial}' belongs to attribute '{WIDGET_KIND}.serial_a'"
        )

    async def test_other_node_attribute_id_is_refused(
        self, client: InfrahubClient, db: InfrahubDatabase, stored: StoredIds
    ) -> None:
        hash_before = _main_hash()

        response = await client.schema.load(
            schemas=[_schema(_node("Other", [{**SERIAL, "name": "stolen_a", "id": stored.serial}]))]
        )

        assert response.errors == _error_body(
            f"{OTHER_KIND}.stolen_a: id '{stored.serial}' belongs to attribute '{WIDGET_KIND}.serial_a'"
        )
        assert "stolen_a" not in registry.schema.get(name=OTHER_KIND).attribute_names
        assert await _vertex_ids(db=db, schema_kind="SchemaAttribute", field_name="stolen_a") == []
        assert await _vertex_ids(db=db, schema_kind="SchemaAttribute", field_name="serial_a") == [stored.serial]
        assert _main_hash() == hash_before

    async def test_node_unknown_id_keeps_stored_id(
        self, client: InfrahubClient, db: InfrahubDatabase, stored: StoredIds
    ) -> None:
        response = await client.schema.load(schemas=[_schema(_node("Widget", [], node_id=str(uuid.uuid4())))])

        assert not response.errors
        assert response.warnings == [_warning(IGNORED_ID_WARNING, kind=WIDGET_KIND, field=None)]
        rows = await NodeManager.query(
            db=db, schema="SchemaNode", filters={"name__value": "Widget", "namespace__value": NAMESPACE}
        )
        assert [row.id for row in rows] == [stored.widget_node]

    async def test_attribute_unknown_id_keeps_stored_id(
        self, client: InfrahubClient, db: InfrahubDatabase, stored: StoredIds
    ) -> None:
        response = await client.schema.load(schemas=[_schema(_node("Widget", [{**SERIAL, "id": str(uuid.uuid4())}]))])

        assert not response.errors
        assert response.warnings == [_warning(IGNORED_ID_WARNING, kind=WIDGET_KIND, field="serial_a")]
        assert registry.schema.get(name=WIDGET_KIND).get_attribute("serial_a").id == stored.serial
        assert await _vertex_ids(db=db, schema_kind="SchemaAttribute", field_name="serial_a") == [stored.serial]
        node = await NodeManager.get_one(db=db, id=stored.widget_data)
        assert node.serial_a.value == "ABC"

    async def test_relationship_unknown_id_keeps_stored_id(
        self, client: InfrahubClient, db: InfrahubDatabase, stored: StoredIds
    ) -> None:
        response = await client.schema.load(schemas=[_schema(_node("Widget", [], [{**TAGS, "id": str(uuid.uuid4())}]))])

        assert not response.errors
        assert response.warnings == [_warning(IGNORED_ID_WARNING, kind=WIDGET_KIND, field="tags_r")]
        assert registry.schema.get(name=WIDGET_KIND).get_relationship("tags_r").id == stored.tags
        assert await _vertex_ids(db=db, schema_kind="SchemaRelationship", field_name="tags_r") == [stored.tags]
        node = await NodeManager.get_one(db=db, id=stored.widget_data)
        peers = await node.tags_r.get_peers(db=db)
        assert list(peers.keys()) == [stored.tag_data]

    async def test_rename_attribute_by_stored_id(
        self, client: InfrahubClient, db: InfrahubDatabase, stored: StoredIds
    ) -> None:
        response = await client.schema.load(
            schemas=[_schema(_node("Widget", [{**MODEL, "name": "hardware_model_a", "id": stored.model}]))]
        )

        assert not response.errors
        assert response.warnings == []
        widget_schema = registry.schema.get(name=WIDGET_KIND)
        assert widget_schema.get_attribute("hardware_model_a").id == stored.model
        assert "model_a" not in widget_schema.attribute_names
        assert await _vertex_ids(db=db, schema_kind="SchemaAttribute", field_name="model_a") == []
        assert await _vertex_ids(db=db, schema_kind="SchemaAttribute", field_name="hardware_model_a") == [stored.model]
        node = await NodeManager.get_one(db=db, id=stored.widget_data)
        assert node.hardware_model_a.value == "X1"

    async def test_remove_attribute_by_stored_id(
        self, client: InfrahubClient, db: InfrahubDatabase, stored: StoredIds
    ) -> None:
        response = await client.schema.load(
            schemas=[_schema(_node("Widget", [{**OLD, "id": stored.old, "state": "absent"}]))]
        )

        assert not response.errors
        assert response.warnings == []
        assert "old_a" not in registry.schema.get(name=WIDGET_KIND).attribute_names
        assert await _vertex_ids(db=db, schema_kind="SchemaAttribute", field_name="old_a") == []

    async def test_deleted_attribute_id_is_refused(
        self, client: InfrahubClient, db: InfrahubDatabase, stored: StoredIds
    ) -> None:
        hash_before = _main_hash()

        response = await client.schema.load(
            schemas=[_schema(_node("Widget", [{**OLD, "name": "new_a", "id": stored.old}]))]
        )

        assert response.errors == _error_body(
            f"{WIDGET_KIND}.new_a: id '{stored.old}' belongs to a schema element that is not on this branch"
        )
        assert "new_a" not in registry.schema.get(name=WIDGET_KIND).attribute_names
        assert await _vertex_ids(db=db, schema_kind="SchemaAttribute", field_name="new_a") == []
        assert _main_hash() == hash_before

    async def test_absent_attribute_loaded_again(
        self, client: InfrahubClient, db: InfrahubDatabase, stored: StoredIds
    ) -> None:
        hash_before = _main_hash()

        response = await client.schema.load(
            schemas=[_schema(_node("Widget", [{**OLD, "id": stored.old, "state": "absent"}]))]
        )

        assert not response.errors
        assert response.warnings == [_warning(SKIPPED_ABSENT_WARNING, kind=WIDGET_KIND, field="old_a")]
        assert response.schema_updated is False
        assert await _vertex_ids(db=db, schema_kind="SchemaAttribute", field_name="old_a") == []
        assert _main_hash() == hash_before

    async def test_other_branch_attribute_id_is_refused(
        self, client: InfrahubClient, db: InfrahubDatabase, stored: StoredIds
    ) -> None:
        await client.branch.create(branch_name=BRANCH_NAME, sync_with_git=False)
        on_branch = await client.schema.load(
            schemas=[_schema(_node("Widget", [{**SERIAL, "name": "branch_a"}]))], branch=BRANCH_NAME
        )
        assert not on_branch.errors
        branch_id = registry.schema.get(name=WIDGET_KIND, branch=BRANCH_NAME).get_attribute("branch_a").id
        hash_before = _main_hash()

        response = await client.schema.load(
            schemas=[_schema(_node("Other", [{**SERIAL, "name": "main_a", "id": branch_id}]))]
        )

        assert response.errors == _error_body(
            f"{OTHER_KIND}.main_a: id '{branch_id}' belongs to a schema element that is not on this branch"
        )
        assert registry.schema.get(name=OTHER_KIND).attribute_names == ["name"]
        assert await _vertex_ids(db=db, schema_kind="SchemaAttribute", field_name="main_a") == []
        assert _main_hash() == hash_before
