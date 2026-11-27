from __future__ import annotations

from dataclasses import dataclass
from operator import itemgetter
from typing import TYPE_CHECKING, Any

import pytest
import yaml
from infrahub_sdk.schema.generated.write import (
    AttributeSchemaWrite,
    GenericSchemaWrite,
    NodeSchemaWrite,
    RelationshipSchemaWrite,
)
from pydantic import BaseModel, TypeAdapter
from structlog.testing import capture_logs

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.query import QueryType
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.registry import registry as graphql_registry
from infrahub.schema.export.exporter import convert_deprecated_attribute_fields
from infrahub.schema.export.models import SchemaExportMode
from infrahub.utils import format_label
from tests.helpers.fixtures import get_repository_dir
from tests.helpers.schema import load_schema
from tests.helpers.schema.export_variations import (
    DERIVED_FROM_UNIQUE_ATTRIBUTE,
    RESTRICTED_NAMESPACE_EXTENSION,
    VARIATION_SCHEMAS,
    merge_variation_schemas,
)
from tests.helpers.schema_cache import install_processed_core_schema_branch
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.schema import SchemaWarning

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.helpers.test_client import InfrahubTestClient

DELETE_VERTICES_WITH_THEIR_FIELDS_QUERY = """
MATCH (n:Node)
WHERE n.uuid IN $ids OR n.kind IN $kinds
OPTIONAL MATCH (n)-[:HAS_ATTRIBUTE]->(attribute:Attribute)
OPTIONAL MATCH (n)-[:IS_RELATED]-(relationship:Relationship)
WITH collect(DISTINCT n) + collect(DISTINCT attribute) + collect(DISTINCT relationship) AS vertices
UNWIND vertices AS vertex
DETACH DELETE vertex
"""

COUNT_OBJECTS_OF_KINDS_QUERY = """
MATCH (n:Node)
WHERE n.kind IN $kinds
RETURN count(n) AS objects
"""


def _user_schema_ids(current: SchemaBranch, core: SchemaBranch) -> list[str]:
    """Return the IDs of the stored schema elements the schema owner added, on user kinds and on core kinds."""
    ids: list[str | None] = []
    for kind in current.node_names + current.generic_names:
        element = current.get(name=kind, duplicate=False)
        if core.has(name=kind):
            core_element = core.get(name=kind, duplicate=False)
            ids.extend(
                attribute.id for attribute in element.attributes if attribute.name not in core_element.attribute_names
            )
            ids.extend(
                relationship.id
                for relationship in element.relationships
                if relationship.name not in core_element.relationship_names
            )
            continue
        ids.append(element.id)
        ids.extend(attribute.id for attribute in element.attributes)
        ids.extend(relationship.id for relationship in element.relationships)
    return sorted({schema_id for schema_id in ids if schema_id})


async def reset_to_core_schema(db: InfrahubDatabase, branch: Branch) -> None:
    """Return the branch to the schema of an empty instance, keeping the objects of the core kinds.

    The stored user-defined schema and the objects of the user-defined kinds are deleted from the database; the
    root, the branches, the core schema and the accounts, tokens, groups and permissions stay, so API clients stay
    logged in.
    """
    current = registry.schema.get_schema_branch(name=branch.name)
    # An empty schema branch lets the cached core schema replace the user-defined one.
    registry.schema.set_schema_branch(name=branch.name, schema=SchemaBranch(cache={}, name=branch.name))
    core = install_processed_core_schema_branch(branch_name=branch.name)

    user_kinds = sorted(set(current.all_names) - set(core.all_names))
    await db.execute_query(
        query=DELETE_VERTICES_WITH_THEIR_FIELDS_QUERY,
        params={"ids": _user_schema_ids(current=current, core=core), "kinds": user_kinds},
        name="reset_to_core_schema",
        type=QueryType.WRITE,
    )

    reloaded = await registry.schema.load_schema_from_db(db=db, branch=branch, schema=core)
    registry.schema.set_schema_branch(name=branch.name, schema=reloaded)
    branch.update_schema_hash()
    await branch.save(db=db)
    graphql_registry.clear_cache()


def core_schema_kinds() -> set[str]:
    """Return the kinds of the nodes and generics that the core schema definitions define."""
    return {
        f"{element['namespace']}{element['name']}"
        for definitions in (internal_schema, core_models, deprecated_models)
        for element_type in ("nodes", "generics")
        for element in definitions.get(element_type, [])
    }


async def fetch_schema(test_client: InfrahubTestClient, token: str, branch: str) -> dict[str, Any]:
    response = await test_client.get(f"/api/schema?branch={branch}", headers={"X-INFRAHUB-KEY": token})
    assert response.status_code == 200, response.text
    return response.json()


def schema_kinds(schema: dict[str, Any]) -> set[str]:
    return {element["namespace"] + element["name"] for element in schema["nodes"] + schema["generics"]}


async def assert_holds_only_the_core_schema(test_client: InfrahubTestClient, token: str, branch: str) -> None:
    kinds = schema_kinds(await fetch_schema(test_client=test_client, token=token, branch=branch))

    assert InfrahubKind.IPNAMESPACE in kinds
    assert sorted(kinds - core_schema_kinds()) == []


def _tag_field_names(schema: dict[str, Any]) -> set[str]:
    tag = next(node for node in schema["nodes"] if node["namespace"] + node["name"] == InfrahubKind.TAG)
    return {field["name"] for field in tag["attributes"] + tag["relationships"]}


async def store_core_schema_of(db: InfrahubDatabase, kinds: list[str]) -> None:
    """Store the core schema of the given kinds in the database, as an instance does for every core kind.

    The test app keeps the core schema in memory only, and a schema extension can only reach a stored kind.
    """
    await load_schema(db=db, schema=SchemaRoot(), update_db=True, limit=kinds)


class TestResetToCoreSchema(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def user_schema(self) -> dict[str, Any]:
        return merge_variation_schemas([DERIVED_FROM_UNIQUE_ATTRIBUTE, RESTRICTED_NAMESPACE_EXTENSION])

    @pytest.fixture(scope="class")
    async def stored_tag_schema(self, db: InfrahubDatabase, initialize_registry: None) -> None:
        await store_core_schema_of(db=db, kinds=[InfrahubKind.TAG])

    async def test_reset_removes_the_user_schema_and_its_objects(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        stored_tag_schema: None,
        client: InfrahubClient,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        user_schema: dict[str, Any],
    ) -> None:
        schema_before_load = await fetch_schema(
            test_client=test_client, token=api_admin_token, branch=default_branch.name
        )
        core_kinds_before_load = schema_kinds(schema_before_load)
        load = await client.schema.load(schemas=[user_schema], wait_until_converged=True)
        assert load.errors == {}
        device = await client.create(kind="DerivedDevice", data={"name": "edge01"})
        await device.save()
        owner = await client.create(kind="TaggedOwner", data={"name": "network-team"})
        await owner.save()
        tag = await client.create(kind=InfrahubKind.TAG, data={"name": "blue", "owner": owner})
        await tag.save()
        loaded_schema = await fetch_schema(test_client=test_client, token=api_admin_token, branch=default_branch.name)
        assert schema_kinds(loaded_schema) - core_kinds_before_load == {"DerivedDevice", "TaggedOwner"}
        assert _tag_field_names(loaded_schema) - _tag_field_names(schema_before_load) == {"external_code", "owner"}

        await reset_to_core_schema(db=db, branch=default_branch)

        schema = await fetch_schema(test_client=test_client, token=api_admin_token, branch=default_branch.name)
        assert schema_kinds(schema) == core_kinds_before_load
        await assert_holds_only_the_core_schema(
            test_client=test_client, token=api_admin_token, branch=default_branch.name
        )
        assert _tag_field_names(schema) == _tag_field_names(schema_before_load)
        objects = await db.execute_query(
            query=COUNT_OBJECTS_OF_KINDS_QUERY, params={"kinds": ["DerivedDevice", "TaggedOwner"]}
        )
        assert objects[0]["objects"] == 0

        await client.schema.all(refresh=True)
        tags = await client.all(kind=InfrahubKind.TAG)
        assert [found.id for found in tags] == [tag.id]

    async def test_user_schema_loads_again_after_a_reset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        user_schema: dict[str, Any],
    ) -> None:
        load = await client.schema.load(schemas=[user_schema], wait_until_converged=True)
        assert load.errors == {}
        devices = await client.all(kind="DerivedDevice")
        assert devices == []

        await reset_to_core_schema(db=db, branch=default_branch)

        await assert_holds_only_the_core_schema(
            test_client=test_client, token=api_admin_token, branch=default_branch.name
        )


EXPORT_BUILT_EVENT = "Schema export built"
VALUE_PUT_BACK_EVENT = "Schema export put back a value that processing changes"
INFRAHUB_VERSION_FIELD = "infrahub_version"
SCHEMA_SECTIONS = ("nodes", "generics", "profiles", "templates")
DISPLAY_LABELS_WARNING = "display_labels are deprecated, use display_label instead"
DEFAULT_FILTER_WARNING = "default_filter is deprecated"
MAX_LENGTH_WARNING = "Use of 'max_length' on attributes is deprecated, use parameters instead"
MIN_LENGTH_WARNING = "Use of 'min_length' on attributes is deprecated, use parameters instead"
LIST_ATTRIBUTE_KIND = "List"
EXPORT_BRANCH_NAME = "schema-export"
LOCATION_NAMESPACE = "Location"
BRANCH_ONLY_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Cabinet",
            "namespace": "Branchonly",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
        }
    ],
}

WarningKey = tuple[str, str, str | None]
ExportedField = tuple[str, str | None, str]


@dataclass(frozen=True)
class SchemaExportRoundTrip:
    """What a schema load, an export, a reset and a load of the export returned, in that order."""

    mode: SchemaExportMode
    source_schema: dict[str, Any]
    export: dict[str, Any]
    repeated_export: dict[str, Any]
    export_logs: list[MutableMapping[str, Any]]
    core_only_schema: dict[str, Any]
    export_after_reset_status: int
    export_after_reset: dict[str, Any]
    target_warnings: list[SchemaWarning]
    target_schema: dict[str, Any]
    target_export: dict[str, Any]


async def fetch_export(
    test_client: InfrahubTestClient,
    token: str,
    branch: str,
    mode: SchemaExportMode,
    namespaces: list[str] | None = None,
) -> dict[str, Any]:
    params: dict[str, str | list[str]] = {"branch": branch, "mode": mode.value}
    if namespaces is not None:
        params["namespaces"] = namespaces
    response = await test_client.get("/api/schema/export", params=params, headers={"X-INFRAHUB-KEY": token})
    assert response.status_code == 200, response.text
    return response.json()


def _kind(element: dict[str, Any]) -> str:
    return element["namespace"] + element["name"]


def _without_ids_and_unset_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_ids_and_unset_values(item) for key, item in value.items() if key != "id" and item is not None
        }
    if isinstance(value, list):
        return [_without_ids_and_unset_values(item) for item in value]
    return value


def _user_elements(schema: dict[str, Any], core_only_schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the elements of a schema read from the API that an empty instance does not hold, in a comparable form.

    IDs, unset values and the element hash are left out, and attributes and relationships are sorted by name,
    because the order of a schema read back from the database can change. The attributes hold their parameters
    in the current form only, because a load stores NumberPool ranges as `ranges` where the source may hold
    `start_range` and `end_range`.
    """
    core_kinds = {_kind(element) for section in SCHEMA_SECTIONS for element in core_only_schema[section]}
    elements: dict[str, dict[str, Any]] = {}
    for section in SCHEMA_SECTIONS:
        for element in schema[section]:
            if _kind(element) in core_kinds:
                continue
            converted = {
                **element,
                "attributes": sorted(
                    (convert_deprecated_attribute_fields(attribute) for attribute in element["attributes"]),
                    key=itemgetter("name"),
                ),
                "relationships": sorted(element["relationships"], key=itemgetter("name")),
            }
            converted.pop("hash")
            elements[_kind(element)] = _without_ids_and_unset_values(converted)
    return elements


def _without_infrahub_version(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key != INFRAHUB_VERSION_FIELD}


def _warning_keys(warnings: list[SchemaWarning]) -> list[WarningKey]:
    return sorted((warning.message, kind.kind, kind.field) for warning in warnings for kind in warning.kinds)


def _expected_load_warnings(document: dict[str, Any]) -> list[WarningKey]:
    """Return the deprecation warnings a load of the document gives.

    The parameters of a List attribute have no length settings, so a List attribute keeps them at the top level.
    """
    expected: list[WarningKey] = []
    for element in document["nodes"] + document["generics"]:
        if "display_labels" in element:
            expected.append((DISPLAY_LABELS_WARNING, _kind(element), None))
        if "default_filter" in element:
            expected.append((DEFAULT_FILTER_WARNING, _kind(element), None))
        for attribute in element.get("attributes", []):
            if attribute["kind"] != LIST_ATTRIBUTE_KIND:
                continue
            if "max_length" in attribute:
                expected.append((MAX_LENGTH_WARNING, _kind(element), attribute["name"]))
            if "min_length" in attribute:
                expected.append((MIN_LENGTH_WARNING, _kind(element), attribute["name"]))
    return sorted(expected)


def _default_valued_fields(model: type[BaseModel], data: dict[str, Any]) -> set[str]:
    return {
        name
        for name, value in data.items()
        if not model.model_fields[name].is_required()
        and value == model.model_fields[name].get_default(call_default_factory=True)
    }


def _exported_default_values(document: dict[str, Any]) -> set[ExportedField]:
    """Return each field of the document's elements, attributes and relationships that holds its default value."""
    attribute_adapter: TypeAdapter[AttributeSchemaWrite] = TypeAdapter(AttributeSchemaWrite)
    fields: set[ExportedField] = set()
    for section, model in (("nodes", NodeSchemaWrite), ("generics", GenericSchemaWrite)):
        for element in document[section]:
            kind = _kind(element)
            fields.update((kind, None, name) for name in _default_valued_fields(model, element))
            for attribute in element.get("attributes", []):
                attribute_model = type(attribute_adapter.validate_python(attribute))
                fields.update(
                    (kind, attribute["name"], name) for name in _default_valued_fields(attribute_model, attribute)
                )
            for relationship in element.get("relationships", []):
                fields.update(
                    (kind, relationship["name"], name)
                    for name in _default_valued_fields(RelationshipSchemaWrite, relationship)
                )
    return fields


def _records(records: list[MutableMapping[str, Any]], event: str) -> list[MutableMapping[str, Any]]:
    return [record for record in records if record["event"] == event]


def _exported_items(document: dict[str, Any]) -> list[tuple[str, str | None, dict[str, Any]]]:
    """Return each exported element, attribute and relationship with the kind and the name that locate it."""
    items: list[tuple[str, str | None, dict[str, Any]]] = []
    for element in document["nodes"] + document["generics"]:
        items.append((_kind(element), None, element))
        items.extend(
            (_kind(element), item["name"], item)
            for collection in ("attributes", "relationships")
            for item in element.get(collection, [])
        )
    return items


def _assert_brief_export_leaves_out_derived_labels_and_unneeded_default_values(
    round_trip: SchemaExportRoundTrip,
) -> None:
    put_back = {
        (record["kind"], record["element"], record["field"])
        for record in _records(round_trip.export_logs, VALUE_PUT_BACK_EVENT)
    }
    derived_labels = [
        (_kind(element), attribute["name"])
        for element in round_trip.export["nodes"] + round_trip.export["generics"]
        for attribute in element.get("attributes", [])
        if attribute.get("label") == format_label(attribute["name"])
    ]

    assert derived_labels == []
    assert sorted(_exported_default_values(round_trip.export) - put_back, key=str) == []


def _assert_full_export_writes_the_label_and_state_of_each_item(round_trip: SchemaExportRoundTrip) -> None:
    items = _exported_items(round_trip.export)

    assert len(items) > len(round_trip.export["nodes"] + round_trip.export["generics"])
    assert [(kind, name) for kind, name, item in items if "label" not in item] == []
    assert {item["state"] for _, _, item in items} == {"present"}
    assert _records(round_trip.export_logs, VALUE_PUT_BACK_EVENT) == []


MODE_ASSERTIONS = {
    SchemaExportMode.BRIEF: _assert_brief_export_leaves_out_derived_labels_and_unneeded_default_values,
    SchemaExportMode.FULL: _assert_full_export_writes_the_label_and_state_of_each_item,
}


class SchemaExportRoundTripTests(TestInfrahubApp):
    """Loads a schema, exports it, returns the instance to an empty schema and loads the export.

    A subclass gives the schema files to load with the class fixture `source_schemas`. The round trip runs once
    per export mode, and the second one starts from the schema that the first one loaded.
    """

    @pytest.fixture(scope="class")
    def source_schemas(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @pytest.fixture(scope="class", params=[pytest.param(mode, id=mode.value) for mode in SchemaExportMode])
    def export_mode(self, request: pytest.FixtureRequest) -> SchemaExportMode:
        return request.param

    @pytest.fixture(scope="class")
    async def round_trip(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        source_schemas: list[dict[str, Any]],
        export_mode: SchemaExportMode,
    ) -> SchemaExportRoundTrip:
        branch = default_branch.name
        source_load = await client.schema.load(schemas=source_schemas, wait_until_converged=True)
        assert source_load.errors == {}
        source_schema = await fetch_schema(test_client=test_client, token=api_admin_token, branch=branch)
        with capture_logs() as export_logs:
            export = await fetch_export(test_client=test_client, token=api_admin_token, branch=branch, mode=export_mode)
        repeated_export = await fetch_export(
            test_client=test_client, token=api_admin_token, branch=branch, mode=export_mode
        )

        await reset_to_core_schema(db=db, branch=default_branch)
        await assert_holds_only_the_core_schema(test_client=test_client, token=api_admin_token, branch=branch)
        core_only_schema = await fetch_schema(test_client=test_client, token=api_admin_token, branch=branch)
        export_after_reset = await test_client.get(
            f"/api/schema/export?branch={branch}&mode={export_mode.value}", headers={"X-INFRAHUB-KEY": api_admin_token}
        )

        target_load = await client.schema.load(schemas=[export], wait_until_converged=True)
        assert target_load.errors == {}
        target_schema = await fetch_schema(test_client=test_client, token=api_admin_token, branch=branch)
        target_export = await fetch_export(
            test_client=test_client, token=api_admin_token, branch=branch, mode=export_mode
        )

        return SchemaExportRoundTrip(
            mode=export_mode,
            source_schema=source_schema,
            export=export,
            repeated_export=repeated_export,
            export_logs=export_logs,
            core_only_schema=core_only_schema,
            export_after_reset_status=export_after_reset.status_code,
            export_after_reset=export_after_reset.json(),
            target_warnings=target_load.warnings,
            target_schema=target_schema,
            target_export=target_export,
        )

    def test_export_loads_to_the_source_schema(
        self, round_trip: SchemaExportRoundTrip, source_schemas: list[dict[str, Any]]
    ) -> None:
        declared_kinds = {
            _kind(element)
            for schema in source_schemas
            for element in schema.get("nodes", []) + schema.get("generics", [])
        }
        source = _user_elements(round_trip.source_schema, round_trip.core_only_schema)
        target = _user_elements(round_trip.target_schema, round_trip.core_only_schema)

        assert {_kind(element) for element in round_trip.export["nodes"] + round_trip.export["generics"]} == (
            declared_kinds
        )
        assert declared_kinds <= set(source)
        assert target == source

    def test_load_of_the_export_gives_only_deprecation_warnings(self, round_trip: SchemaExportRoundTrip) -> None:
        assert _warning_keys(round_trip.target_warnings) == _expected_load_warnings(round_trip.export)

    def test_export_is_the_same_when_repeated_and_after_a_load(self, round_trip: SchemaExportRoundTrip) -> None:
        assert _without_infrahub_version(round_trip.repeated_export) == _without_infrahub_version(round_trip.export)
        assert _without_infrahub_version(round_trip.target_export) == _without_infrahub_version(round_trip.export)

    def test_export_of_an_empty_instance_holds_no_schema(self, round_trip: SchemaExportRoundTrip) -> None:
        assert round_trip.export_after_reset_status == 200
        assert (round_trip.export_after_reset["nodes"], round_trip.export_after_reset["generics"]) == ([], [])

    def test_export_holds_the_values_its_mode_writes(self, round_trip: SchemaExportRoundTrip) -> None:
        MODE_ASSERTIONS[round_trip.mode](round_trip)

    def test_export_reports_its_time_and_pass_count(
        self, round_trip: SchemaExportRoundTrip, request: pytest.FixtureRequest
    ) -> None:
        built = _records(round_trip.export_logs, EXPORT_BUILT_EVENT)

        assert [record["mode"] for record in built] == [round_trip.mode.value]
        print(
            f"{request.cls.__name__} {round_trip.mode.value}: schema export in {built[0]['duration_seconds']} s, "
            f"{built[0]['passes']} passes"
        )

    async def test_export_rejects_an_unknown_mode(
        self, test_client: InfrahubTestClient, api_admin_token: str, default_branch: Branch
    ) -> None:
        response = await test_client.get(
            f"/api/schema/export?branch={default_branch.name}&mode=OTHER", headers={"X-INFRAHUB-KEY": api_admin_token}
        )

        assert response.status_code == 422
        assert response.json() == {
            "detail": [
                {
                    "type": "enum",
                    "loc": ["query", "mode"],
                    "msg": "Input should be 'BRIEF' or 'FULL'",
                    "input": "OTHER",
                    "ctx": {"expected": "'BRIEF' or 'FULL'"},
                }
            ]
        }

    async def test_account_with_the_default_read_access_can_export(
        self, test_client: InfrahubTestClient, api_unprivileged_token: str, default_branch: Branch
    ) -> None:
        headers = {"X-INFRAHUB-KEY": api_unprivileged_token}

        schema = await test_client.get(f"/api/schema?branch={default_branch.name}", headers=headers)
        export = await test_client.get(f"/api/schema/export?branch={default_branch.name}", headers=headers)

        assert (schema.status_code, export.status_code) == (200, 200)


class TestSchemaExportOfBaseModels(SchemaExportRoundTripTests):
    @pytest.fixture(scope="class")
    def source_schemas(self) -> list[dict[str, Any]]:
        models_dir = get_repository_dir() / "models" / "base"
        return [yaml.safe_load(path.read_text()) for path in sorted(models_dir.glob("*.yml"))]

    def test_number_pool_keeps_its_range(self, round_trip: SchemaExportRoundTrip) -> None:
        service = next(generic for generic in round_trip.target_schema["generics"] if _kind(generic) == "InfraService")
        identifier = next(attribute for attribute in service["attributes"] if attribute["name"] == "service_identifier")

        assert identifier["parameters"]["ranges"] == [{"start": 100, "end": 10000, "weight": None}]

    async def test_export_of_one_namespace_writes_its_entries_as_the_unfiltered_export(
        self,
        round_trip: SchemaExportRoundTrip,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        default_branch: Branch,
    ) -> None:
        location_export = await fetch_export(
            test_client=test_client,
            token=api_admin_token,
            branch=default_branch.name,
            mode=round_trip.mode,
            namespaces=[LOCATION_NAMESPACE],
        )

        elements = location_export["nodes"] + location_export["generics"]
        peers_outside_the_namespace = {
            relationship["peer"]
            for element in elements
            for relationship in element.get("relationships", [])
            if not relationship["peer"].startswith(LOCATION_NAMESPACE)
        }
        assert sorted({element["namespace"] for element in elements}) == [LOCATION_NAMESPACE]
        assert peers_outside_the_namespace == {"InfraDevice", "InfraVLAN", "InfraCircuitEndpoint", "BuiltinTag"}
        for element_type in ("nodes", "generics"):
            assert location_export[element_type] == [
                element
                for element in round_trip.target_export[element_type]
                if element["namespace"] == LOCATION_NAMESPACE
            ]

    async def test_export_of_an_unknown_namespace_names_the_namespace_unlike_an_unknown_url(
        self,
        round_trip: SchemaExportRoundTrip,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        default_branch: Branch,
    ) -> None:
        headers = {"X-INFRAHUB-KEY": api_admin_token}

        export = await test_client.get(
            "/api/schema/export",
            params={"branch": default_branch.name, "namespaces": [LOCATION_NAMESPACE, "Locaton", "Core"]},
            headers=headers,
        )
        unknown_url = await test_client.get("/api/schema/export/unknown", headers=headers)

        assert (export.status_code, unknown_url.status_code) == (404, 404)
        assert export.json() == {
            "data": None,
            "errors": [
                {
                    "message": f"The namespace 'Locaton' does not exist on the branch '{default_branch.name}'",
                    "extensions": {"namespace": "Locaton", "code": 404},
                },
                {
                    "message": "The namespace 'Core' is reserved for Infrahub and cannot be exported",
                    "extensions": {"namespace": "Core", "code": 404},
                },
            ],
        }
        assert unknown_url.json() == {
            "data": None,
            "errors": [
                {
                    "message": "The requested endpoint /api/schema/export/unknown does not exist",
                    "extensions": {"code": 404},
                }
            ],
        }


class TestSchemaExportOfVariationSchemas(SchemaExportRoundTripTests):
    @pytest.fixture(scope="class")
    async def source_schemas(self, db: InfrahubDatabase, initialize_registry: None) -> list[dict[str, Any]]:
        await store_core_schema_of(db=db, kinds=[InfrahubKind.TAG])
        return [merge_variation_schemas(VARIATION_SCHEMAS)]

    def test_number_pool_keeps_its_range(self, round_trip: SchemaExportRoundTrip) -> None:
        circuit = next(node for node in round_trip.target_schema["nodes"] if _kind(node) == "PoolCircuit")
        ranges = {
            attribute["name"]: attribute["parameters"]["ranges"]
            for attribute in circuit["attributes"]
            if attribute["kind"] == "NumberPool"
        }

        assert ranges == {
            "vlan_id": [{"start": 100, "end": 200, "weight": None}],
            "vni": [{"start": 5000, "end": None, "weight": None}],
            "circuit_index": [{"start": 1, "end": 50, "weight": 10}, {"start": 51, "end": 100, "weight": None}],
        }

    async def test_export_of_a_branch_returns_the_schema_of_that_branch(
        self,
        round_trip: SchemaExportRoundTrip,
        client: InfrahubClient,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        default_branch: Branch,
    ) -> None:
        branch_name = f"{EXPORT_BRANCH_NAME}-{round_trip.mode.value.lower()}"
        await client.branch.create(branch_name=branch_name, sync_with_git=False)
        load = await client.schema.load(schemas=[BRANCH_ONLY_SCHEMA], branch=branch_name, wait_until_converged=True)
        assert load.errors == {}

        branch_export = await fetch_export(
            test_client=test_client, token=api_admin_token, branch=branch_name, mode=round_trip.mode
        )
        main_export = await fetch_export(
            test_client=test_client, token=api_admin_token, branch=default_branch.name, mode=round_trip.mode
        )

        branch_kinds = {_kind(element) for element in branch_export["nodes"] + branch_export["generics"]}
        main_kinds = {_kind(element) for element in main_export["nodes"] + main_export["generics"]}
        assert branch_kinds - main_kinds == {"BranchonlyCabinet"}
        assert main_kinds - branch_kinds == set()
