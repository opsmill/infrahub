from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .catalogue import CATALOGUE

if TYPE_CHECKING:
    from pathlib import Path

CATALOGUE_VERSION = "1"
JSON_SCHEMA_VERSION = "https://json-schema.org/draft/2020-12/schema"


def export_catalogue() -> dict[str, Any]:
    """Render the in-process catalogue into the published JSON Schema document."""
    codes: dict[str, Any] = {}
    for code, entry in CATALOGUE.items():
        data_schema = entry.payload_model.model_json_schema()
        data_schema.pop("$defs", None)
        data_schema.setdefault("additionalProperties", False)
        if "required" not in data_schema:
            data_schema["required"] = []
        codes[code] = {
            "description": entry.description,
            "stability": entry.stability,
            "http_status": entry.http_status,
            "data_schema": data_schema,
        }

    return {
        "$schema": JSON_SCHEMA_VERSION,
        "infrahub_catalogue_version": CATALOGUE_VERSION,
        "codes": codes,
    }


def write_catalogue(destination: Path) -> Path:
    """Serialize the catalogue to ``destination`` and return the absolute path."""
    payload = export_catalogue()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return destination.resolve()
