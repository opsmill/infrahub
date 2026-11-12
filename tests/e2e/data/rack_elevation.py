"""Rack elevation slice: two racks, five item types and eight items.

The schema is the option 2 test schema, with ``rack_elevation`` mappings on ``schema-library`` kind names; the dataset is
described in ``backend/tests/component/rack_elevation/dataset.py``. The schema is loaded on its own, not on top of
``schema_base``, because the base ``LocationRack`` has a Text height and a mandatory parent site.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from data.common import save_with_retry
from data.handles import RackElevationHandle

if TYPE_CHECKING:
    from types import ModuleType

    from infrahub_sdk import InfrahubClient

BRANCH = "main"
COMPONENT_DIR = Path(__file__).resolve().parents[3] / "backend" / "tests" / "component" / "rack_elevation"
SCHEMA_FILE = COMPONENT_DIR / "schemas" / "option_2.yml"
DATASET_FILE = COMPONENT_DIR / "dataset.py"

TYPE_RELATIONSHIP_BY_KIND = {"DcimDevice": "device_type", "DcimRackAccessory": "accessory_type"}


def _load_dataset() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rack_elevation_dataset", DATASET_FILE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
async def data_rack_elevation(
    infrahub_client: InfrahubClient,
    data_client: InfrahubClient,
    infrahub_provisioned_externally: bool,
) -> RackElevationHandle:
    if infrahub_provisioned_externally:
        return RackElevationHandle.external()

    response = await infrahub_client.schema.load(
        schemas=[yaml.safe_load(SCHEMA_FILE.read_text(encoding="utf-8"))], wait_until_converged=True
    )
    if response.errors:
        raise RuntimeError(f"Rack elevation schema failed to load: {response.errors}")

    dataset = _load_dataset()
    racks = {}
    for rack in dataset.RACKS:
        racks[rack.name] = await data_client.create(
            branch=BRANCH, kind=dataset.RACK_KIND, name=rack.name, height=rack.u_height
        )
        await save_with_retry(obj=racks[rack.name])

    types = {}
    for item_type in dataset.TYPES:
        types[item_type.name] = await data_client.create(
            branch=BRANCH,
            kind=item_type.kind,
            name=item_type.name,
            height=item_type.u_height,
            full_depth=item_type.full_depth,
            weight=item_type.weight,
        )
        await save_with_retry(obj=types[item_type.name])

    items = {}
    for item in dataset.ITEMS:
        data: dict[str, Any] = {"name": item.name, "location": racks[item.rack_name]}
        if item.role:
            data["role"] = item.role
        if item.type_name:
            data[TYPE_RELATIONSHIP_BY_KIND[item.kind]] = types[item.type_name]
        if item.position is not None:
            data["position"] = item.position
            data["rack_face"] = item.face
        items[item.name] = await data_client.create(branch=BRANCH, kind=item.kind, **data)
        await save_with_retry(obj=items[item.name])

    return RackElevationHandle(
        racks={name: node.id for name, node in racks.items()},
        types={name: node.id for name, node in types.items()},
        items={name: node.id for name, node in items.items()},
    )
