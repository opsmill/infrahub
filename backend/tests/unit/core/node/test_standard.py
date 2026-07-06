from typing import Optional

from pydantic import BaseModel

from infrahub.core.constants import NULL_VALUE
from infrahub.core.node.standard import StandardNode


class Nested(BaseModel):
    value: str = "nested"


class NullableFieldsNode(StandardNode):
    plain: str = "plain"
    optional_syntax: Optional[str] = None  # noqa: UP045
    union_syntax: str | None = None
    optional_int: int | None = None
    nested: Nested | None = None
    items: list[str] = []


def test_guess_field_type_resolves_both_nullable_syntaxes() -> None:
    fields = NullableFieldsNode.model_fields

    assert NullableFieldsNode.guess_field_type(fields["plain"]) is str
    assert NullableFieldsNode.guess_field_type(fields["optional_syntax"]) is str
    assert NullableFieldsNode.guess_field_type(fields["union_syntax"]) is str
    assert NullableFieldsNode.guess_field_type(fields["optional_int"]) is int
    assert NullableFieldsNode.guess_field_type(fields["nested"]) is Nested
    assert NullableFieldsNode.guess_field_type(fields["items"]) is str


def test_to_db_serializes_nullable_fields_of_both_syntaxes() -> None:
    node = NullableFieldsNode(union_syntax="set", nested=Nested())

    data = node.to_db()

    assert data["plain"] == "plain"
    assert data["optional_syntax"] == NULL_VALUE
    assert data["union_syntax"] == "set"
    assert data["optional_int"] == NULL_VALUE
    assert data["nested"] == Nested().model_dump_json()
    assert data["items"] == []
