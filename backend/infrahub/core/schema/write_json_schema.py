"""Shape the JSON Schema document published for a user-facing schema file.

``model_json_schema()`` describes only what pydantic can express. The write models set
``extra="ignore"`` because unknown-field policy is applied imperatively when a schema is loaded,
so nothing in the emitted document forbids an undeclared key: an editor validating against it
accepts a typo the load endpoint rejects. Closing every object restores that check.

Read-only fields have to be re-declared alongside it. The load endpoint accepts one, drops the
value and reports a warning, so a closed document that simply omitted them would turn a schema
read back from Infrahub into a file full of errors. JSON Schema has no warning level, and
``deprecated`` is its nearest equivalent: accepted, carrying a message, but not to be written.
"""

from __future__ import annotations

from typing import Any

from infrahub_sdk.schema.generated.contract import READ_ONLY_FIELDS
from infrahub_sdk.schema.generated.write import InfrahubSchemaWrite

ROOT_CLASS_NAME = InfrahubSchemaWrite.__name__
"""Write class the exported root describes. Its own title cannot serve: the export renames it."""

READ_ONLY_MESSAGE = "'{name}' is a read-only field, the submitted value is ignored"
"""Worded as the load endpoint words the same finding, so both tell the user one story."""

DEPRECATED_MESSAGES = {"display_labels": "display_labels are deprecated use display_label instead"}
"""Message for a writable field that is on its way out, keyed by field name wherever it appears."""


def _deprecate(definition: dict[str, Any], message: str) -> None:
    definition["deprecated"] = True
    # Non-standard, and the only keyword yaml-language-server renders a message from.
    definition["deprecationMessage"] = message


def _harden_definition(definition: dict[str, Any], class_name: str) -> None:
    if definition.get("type") != "object":
        return

    properties = definition.setdefault("properties", {})

    for name in sorted(READ_ONLY_FIELDS.get(class_name, frozenset())):
        # A name the table lists that the class declares anyway belongs to a sibling variant of a
        # discriminated union, which owns it as a writable field. Leave that definition alone.
        if name in properties:
            continue
        message = READ_ONLY_MESSAGE.format(name=name)
        properties[name] = {"description": message}
        _deprecate(definition=properties[name], message=message)

    for name, message in DEPRECATED_MESSAGES.items():
        if name in properties:
            _deprecate(definition=properties[name], message=message)

    definition["additionalProperties"] = False


def build_write_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Close every object in a generated write JSON Schema, keeping read-only fields accepted.

    Args:
        schema: The document generated for the write root.

    Returns:
        The document, mutated in place and returned for convenience.

    """
    _harden_definition(definition=schema, class_name=ROOT_CLASS_NAME)
    for class_name, definition in schema.get("$defs", {}).items():
        _harden_definition(definition=definition, class_name=class_name)
    return schema
