from __future__ import annotations

from infrahub.core.manager import get_kind_str
from infrahub.core.protocols import CoreMenuItem
from infrahub.core.schema import NodeSchema


def test_get_kind_str_returns_string_unchanged() -> None:
    assert get_kind_str("BuiltinTag") == "BuiltinTag"


def test_get_kind_str_resolves_protocol_class_to_name() -> None:
    assert get_kind_str(CoreMenuItem) == "CoreMenuItem"


def test_get_kind_str_reads_kind_from_schema_object() -> None:
    assert get_kind_str(NodeSchema(name="Widget", namespace="Test")) == "TestWidget"


def test_get_kind_str_falls_back_for_unknown_input() -> None:
    assert get_kind_str(None) == "Unknown kind"
