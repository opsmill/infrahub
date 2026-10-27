from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.exceptions import SchemaNotFoundError

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

    from .model import SchemaConstraintValidatorRequest


def get_kinds_with_previous_names(
    db: InfrahubDatabase, request: SchemaConstraintValidatorRequest, kinds: list[str]
) -> list[str]:
    """Return the kinds of the candidate schema, plus the names the same schemas have on the branch and its origin.

    Stored nodes keep the label of a renamed kind until its migration runs on each branch, so a check that compares
    labels with a kind accepts every name the schema has had.
    """
    current_schemas = [
        db.schema.get_schema_branch(name=name)
        for name in dict.fromkeys([request.branch.name, request.branch.origin_branch])
    ]
    names = set(kinds)
    for kind in kinds:
        schema_id = request.schema_branch.get(name=kind, duplicate=False).id
        if not schema_id:
            continue
        for current_schema in current_schemas:
            try:
                names.add(current_schema.get_by_id(id=schema_id, duplicate=False).kind)
            except SchemaNotFoundError:
                continue
    return sorted(names)
