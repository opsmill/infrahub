from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from infrahub import __version__
from infrahub.api.dependencies import get_branch_dep, get_current_user
from infrahub.api.schema import router
from infrahub.core.branch import Branch
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.manager import SchemaManager
from infrahub.schema.export.exporter import build_core_schema_baseline

BRANCH_NAME = "main"
DEVICE_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Device",
            "namespace": "Testing",
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        }
    ],
}


@pytest.fixture
def schema_api_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    schema_branch = build_core_schema_baseline(BRANCH_NAME)
    schema_branch.load_schema(schema=SchemaRoot(**DEVICE_SCHEMA))
    schema_branch.process()
    manager = SchemaManager()
    manager.set_schema_branch(name=BRANCH_NAME, schema=schema_branch)
    monkeypatch.setattr(registry, "_schema", manager)

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_branch_dep] = lambda: Branch(name=BRANCH_NAME)
    app.dependency_overrides[get_current_user] = lambda: None
    return TestClient(app)


def test_export_route_returns_only_the_keys_the_export_kept(schema_api_client: TestClient) -> None:
    response = schema_api_client.get("/api/schema/export")

    assert response.status_code == 200
    assert response.json() == {
        "version": "1.0",
        "infrahub_version": __version__,
        "generics": [],
        "nodes": [
            {
                "name": "Device",
                "namespace": "Testing",
                "human_friendly_id": ["name__value"],
                "uniqueness_constraints": [["name__value"]],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            }
        ],
    }


def test_schema_kind_route_still_serves_a_kind(schema_api_client: TestClient) -> None:
    response = schema_api_client.get("/api/schema/TestingDevice")

    assert response.status_code == 200
    assert response.json()["kind"] == "TestingDevice"
