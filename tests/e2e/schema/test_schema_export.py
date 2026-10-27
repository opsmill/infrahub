"""The schema exported by a running instance checks against that instance with no change."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from constants import BASE_SCHEMA_FILES

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.schema import SchemaExportMode

MODELS_BASE_DIR = Path(__file__).resolve().parents[3] / "models" / "base"


class TestSchemaExport:
    @pytest.mark.parametrize("mode", ["brief", "full"])
    async def test_export_checks_with_no_change(
        self, infrahub_client: InfrahubClient, schema_base: None, mode: SchemaExportMode
    ) -> None:
        base_schemas = [
            yaml.safe_load((MODELS_BASE_DIR / filename).read_text(encoding="utf-8")) for filename in BASE_SCHEMA_FILES
        ]
        _, base_response = await infrahub_client.schema.check(schemas=base_schemas)
        assert base_response is not None

        exported = await infrahub_client.schema.export(mode=mode)
        success, response = await infrahub_client.schema.check(
            schemas=[exported.model_dump(mode="json", exclude_unset=True)]
        )

        assert success is True
        assert response is not None
        assert response["diff"] == {"added": {}, "changed": {}, "removed": {}}
        # The base schemas use deprecated fields themselves; the export may only repeat those warnings.
        assert {warning["message"] for warning in response["warnings"]} <= {
            warning["message"] for warning in base_response["warnings"]
        }
