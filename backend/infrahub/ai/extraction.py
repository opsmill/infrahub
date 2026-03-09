from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infrahub_sdk.schema import MainSchemaTypesAPI

log = logging.getLogger(__name__)

# Attributes inherited from CoreFileObject that should never be extracted
_FILE_OBJECT_BASE_ATTRIBUTES = frozenset({"file_name", "checksum", "file_size", "file_type", "storage_id"})

# Attribute kinds that Claude cannot meaningfully extract from a document
_NON_EXTRACTABLE_KINDS = frozenset({"ID", "Password", "HashedPassword", "NumberPool", "File"})

_KIND_FORMAT_HINTS: dict[str, str] = {
    "DateTime": "ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)",
    "Email": "valid email address",
    "URL": "valid URL",
    "MacAddress": "MAC address (e.g. 00:1A:2B:3C:4D:5E)",
    "IPHost": "IP address with optional prefix length (e.g. 192.168.1.1/24)",
    "IPNetwork": "IP network in CIDR notation (e.g. 192.168.1.0/24)",
    "Color": "hex color code (e.g. #FF5733)",
    "Number": "numeric value (integer or float)",
    "Bandwidth": "numeric value in bits per second",
    "Boolean": "true or false",
    "Checkbox": "true or false",
    "List": "JSON array of strings",
    "JSON": "JSON object",
}


@dataclass
class ExtractableAttribute:
    name: str
    kind: str
    description: str | None
    choices: list[str] | None = None


@dataclass
class ExtractableRelationship:
    name: str
    peer: str
    description: str | None
    peer_choices: list[str] | None = None


def get_extractable_relationships(schema: MainSchemaTypesAPI) -> list[ExtractableRelationship]:
    """Return the list of cardinality:one Attribute-kind relationships Claude can extract.

    Only includes relationships that are not read-only.
    """
    result: list[ExtractableRelationship] = []
    for rel in schema.relationships:
        if rel.kind != "Attribute":
            continue
        if rel.cardinality != "one":
            continue
        if getattr(rel, "read_only", False):
            continue
        result.append(
            ExtractableRelationship(
                name=rel.name,
                peer=rel.peer,
                description=rel.description,
            )
        )
    return result


def get_extractable_attributes(schema: MainSchemaTypesAPI) -> list[ExtractableAttribute]:
    """Return the list of schema attributes that Claude can extract from a document.

    Excludes CoreFileObject base attributes, read-only attributes, required-but-not-optional
    attributes that shouldn't be extracted, and kinds that are not meaningful for extraction.
    """
    result: list[ExtractableAttribute] = []
    for attr in schema.attributes:
        if attr.name in _FILE_OBJECT_BASE_ATTRIBUTES:
            continue
        if attr.kind in _NON_EXTRACTABLE_KINDS:
            continue
        if getattr(attr, "read_only", False):
            continue

        choices: list[str] | None = None
        if attr.kind == "Dropdown" and attr.choices:
            choices = [c["value"] if isinstance(c, dict) else str(c) for c in attr.choices]

        result.append(
            ExtractableAttribute(
                name=attr.name,
                kind=attr.kind,
                description=attr.description,
                choices=choices,
            )
        )
    return result


def build_extraction_prompt(
    attributes: list[ExtractableAttribute],
    file_name: str,
    file_type: str,
    relationships: list[ExtractableRelationship] | None = None,
) -> str:
    """Build a system prompt instructing Claude to extract the given attributes and relationships."""
    lines = [
        "You are analyzing a document to extract structured data.",
        f"The document is a '{file_type}' file named '{file_name}'.",
        "",
        "Extract the following fields and return them as a single JSON object.",
        "Rules:",
        "- Use null for any field you cannot determine from the document.",
        "- Do NOT invent or guess values; only extract what is clearly stated.",
        "- Return ONLY the JSON object, no explanation or markdown.",
        "",
        "Fields to extract:",
    ]

    for attr in attributes:
        parts = [f"  - {attr.name}"]
        if attr.description:
            parts.append(f"({attr.description})")

        fmt = _KIND_FORMAT_HINTS.get(attr.kind)
        if fmt:
            parts.append(f"[{fmt}]")
        elif attr.choices:
            parts.append(f"[one of: {', '.join(attr.choices)}]")

        lines.append(" ".join(parts))

    if relationships:
        lines.append("")
        lines.append(
            "Related object fields"
            " (return the EXACT name from the provided choices that best matches the document, or null):"
        )
        for rel in relationships:
            parts = [f"  - {rel.name}"]
            if rel.description:
                parts.append(f"({rel.description})")
            if rel.peer_choices:
                parts.append(f"[one of: {', '.join(rel.peer_choices)}]")
            else:
                parts.append(f"[name of a {rel.peer}]")
            lines.append(" ".join(parts))

    return "\n".join(lines)


def parse_extraction_response(
    response_text: str,
    attributes: list[ExtractableAttribute],
    relationships: list[ExtractableRelationship] | None = None,
) -> dict[str, Any]:
    """Parse Claude's JSON response and return a dict of field_name -> value.

    Only includes fields (attributes and relationships) that are in the expected list
    and have non-null values.
    """
    try:
        raw = json.loads(response_text.strip())
    except json.JSONDecodeError:
        # Try to extract JSON from the response if there's surrounding text
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                raw = json.loads(response_text[start:end])
            except json.JSONDecodeError:
                log.warning("Claude returned non-JSON response: %s", response_text[:200])
                return {}
        else:
            log.warning("Claude returned non-JSON response: %s", response_text[:200])
            return {}

    if not isinstance(raw, dict):
        log.warning("Claude returned unexpected JSON type: %s", type(raw).__name__)
        return {}

    valid_names = {a.name for a in attributes} | {r.name for r in (relationships or [])}
    return {k: v for k, v in raw.items() if k in valid_names and v is not None}
