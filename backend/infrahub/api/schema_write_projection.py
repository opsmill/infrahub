"""Project a schema-load payload onto the user-facing write contract.

A load payload may carry read-only and internal fields (a schema read back from Infrahub, or a
full internal model dump used by tests). Those fields are legitimate — they are validated against
the internal schema first — but the strict write models reject them. This projection keeps only the
write-settable fields, resolving the per-kind attribute and computed-attribute discriminated unions
so each kind keeps the fields valid for it. It runs only after the internal validation has already
rejected genuinely unknown or forbidden fields, so dropping non-write keys never hides a mistake.
"""

from __future__ import annotations

import functools
import types
import typing
from typing import Any

from infrahub_sdk.schema.generated.write import InfrahubSchemaWrite
from pydantic import BaseModel
from pydantic.fields import FieldInfo

_UNION_ORIGINS = {typing.Union, types.UnionType}
_SEQUENCE_ORIGINS = {list, tuple}


def project_to_write_contract(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``schema`` containing only fields accepted by the write contract."""
    if not isinstance(schema, dict):
        return schema
    return _project_model(schema, InfrahubSchemaWrite)


@functools.cache
def _resolved_hints(model: type[BaseModel]) -> dict[str, Any]:
    # ``model_fields[...].annotation`` leaves module-level Annotated aliases (the discriminated
    # unions) as unresolved forward references; ``get_type_hints`` resolves them with the metadata.
    return typing.get_type_hints(model, include_extras=True)


def _project_model(data: Any, model: type[BaseModel]) -> Any:
    if not isinstance(data, dict):
        return data
    hints = _resolved_hints(model)
    projected: dict[str, Any] = {}
    for name, info in model.model_fields.items():
        key = name if name in data else (info.alias if info.alias in data else None)
        if key is None:
            continue
        discriminator = info.discriminator if isinstance(info.discriminator, str) else None
        projected[key] = _project_value(data[key], hints.get(name, info.annotation), discriminator)
    return projected


def _project_value(value: Any, annotation: Any, discriminator: str | None = None) -> Any:
    # Annotated[...] (used for the discriminated unions): unwrap to the base + its discriminator.
    if hasattr(annotation, "__metadata__"):
        nested = next(
            (
                m.discriminator
                for m in annotation.__metadata__
                if isinstance(m, FieldInfo) and isinstance(m.discriminator, str)
            ),
            None,
        )
        return _project_value(value, annotation.__origin__, nested or discriminator)

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin in _UNION_ORIGINS:
        members = [a for a in args if a is not type(None)]
        if discriminator and isinstance(value, dict):
            member = _pick_variant(members, discriminator, value)
            if member is not None:
                return _project_model(value, member)
        return _project_value(value, members[0]) if len(members) == 1 else value

    if origin in _SEQUENCE_ORIGINS and args and isinstance(value, list):
        return [_project_value(item, args[0]) for item in value]

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _project_model(value, annotation)

    return value


def _pick_variant(members: list[Any], discriminator: str, value: dict[str, Any]) -> type[BaseModel] | None:
    target = str(getattr(value.get(discriminator), "value", value.get(discriminator)))
    for member in members:
        if not (isinstance(member, type) and issubclass(member, BaseModel)):
            continue
        field = member.model_fields.get(discriminator)
        if field is not None and target in {str(getattr(a, "value", a)) for a in typing.get_args(field.annotation)}:
            return member
    return None
