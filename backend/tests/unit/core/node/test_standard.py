from typing import Optional, Union

from pydantic import BaseModel

from infrahub.core.constants import NULL_VALUE
from infrahub.core.node.standard import StandardNode


class Nested(BaseModel):
    value: str = "nested"


class NullableFieldsNode(StandardNode):
    plain: str = "plain"
    optional_syntax: Optional[str] = None  # noqa: UP045
    union_syntax: str | None = None
    # `None | X` / `Union[None, X]` are forbidden by RUF036 in real code; constructed here only to
    # prove guess_field_type resolves the wrapped type regardless of union member order.
    reversed_union_syntax: None | int = None  # noqa: RUF036
    reversed_optional_syntax: Union[None, str] = None  # noqa: RUF036, UP007
    optional_int: int | None = None
    nested: Nested | None = None
    items: list[str] = []


def test_guess_field_type_resolves_both_nullable_syntaxes() -> None:
    fields = NullableFieldsNode.model_fields

    assert NullableFieldsNode.guess_field_type(fields["plain"]) is str
    assert NullableFieldsNode.guess_field_type(fields["optional_syntax"]) is str
    assert NullableFieldsNode.guess_field_type(fields["union_syntax"]) is str
    # The None member may appear first; the wrapped type must resolve regardless of union order.
    assert NullableFieldsNode.guess_field_type(fields["reversed_union_syntax"]) is int
    assert NullableFieldsNode.guess_field_type(fields["reversed_optional_syntax"]) is str
    assert NullableFieldsNode.guess_field_type(fields["optional_int"]) is int
    assert NullableFieldsNode.guess_field_type(fields["nested"]) is Nested
    assert NullableFieldsNode.guess_field_type(fields["items"]) is str


def test_to_db_serializes_nullable_fields_of_both_syntaxes() -> None:
    node = NullableFieldsNode(union_syntax="set", reversed_union_syntax=7, nested=Nested())

    data = node.to_db()

    assert data["plain"] == "plain"
    assert data["optional_syntax"] == NULL_VALUE
    assert data["union_syntax"] == "set"
    assert data["reversed_union_syntax"] == 7
    assert data["reversed_optional_syntax"] == NULL_VALUE
    assert data["optional_int"] == NULL_VALUE
    assert data["nested"] == Nested().model_dump_json()
    assert data["items"] == []
