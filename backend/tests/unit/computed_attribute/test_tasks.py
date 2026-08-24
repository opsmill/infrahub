from copy import deepcopy
from typing import Any

from infrahub.computed_attribute.tasks import _partition_transform_results, _python_transform_attributes
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.recompute.bulk_write import AttributeValueWrite
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from tests.helpers.schema import TSHIRT


def _write(node_id: str, value: Any) -> AttributeValueWrite:
    return AttributeValueWrite(node_id=node_id, field="desc", value=value)


def _two_python_attributes() -> NodeSchema:
    """A kind carrying two Python computed attributes, plus a Jinja2 one."""
    node_schema = deepcopy(TSHIRT)
    slogan = deepcopy(node_schema.get_attribute(name="pitch"))
    slogan.name = "slogan"
    slogan.computed_attribute = ComputedAttribute(kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform="TShirtSlogan")
    node_schema.attributes.append(slogan)
    return node_schema


def test_only_the_requested_python_attribute_is_selected() -> None:
    """A kind with two attributes would otherwise run its transform twice per submission."""
    node_schema = _two_python_attributes()

    pitch = _python_transform_attributes(node_schema=node_schema, attribute_name="pitch")
    slogan = _python_transform_attributes(node_schema=node_schema, attribute_name="slogan")

    assert list(pitch) == ["pitch"]
    assert pitch["pitch"].transform == "TShirtPitch"
    assert list(slogan) == ["slogan"]
    assert slogan["slogan"].transform == "TShirtSlogan"


def test_a_jinja2_attribute_selects_nothing() -> None:
    """The flow only knows how to run a transform, so a Jinja2 attribute is not its work."""
    assert _python_transform_attributes(node_schema=_two_python_attributes(), attribute_name="description") == {}


def test_an_unknown_attribute_selects_nothing() -> None:
    assert _python_transform_attributes(node_schema=_two_python_attributes(), attribute_name="missing") == {}


def test_partition_transform_results_persists_only_string_values() -> None:
    """A string value is persisted; a None or non-string value is skipped so the prior value stays."""
    ok = _write("n1", "hello")
    null_value = _write("n2", None)
    wrong_type = _write("n3", 42)

    writes, skipped = _partition_transform_results([("n1", ok), ("n2", null_value), ("n3", wrong_type)])

    assert writes == [ok]
    reasons = dict(skipped)
    assert list(reasons) == ["n2", "n3"]
    assert "NoneType" in reasons["n2"]
    assert "int" in reasons["n3"]


def test_partition_transform_results_isolates_a_failed_node() -> None:
    """A node whose transform raised is skipped without dropping the healthy nodes' writes."""
    ok1 = _write("n1", "a")
    ok2 = _write("n3", "b")

    writes, skipped = _partition_transform_results([("n1", ok1), ("n2", RuntimeError("boom")), ("n3", ok2)])

    assert writes == [ok1, ok2]
    assert len(skipped) == 1
    assert skipped[0][0] == "n2"
    assert "boom" in skipped[0][1]


def test_partition_transform_results_handles_empty() -> None:
    assert _partition_transform_results([]) == ([], [])
