import inspect
from typing import Any

import pytest

from infrahub.computed_attribute.tasks import (
    _partition_transform_results,
    _python_transform_attribute,
    process_transform,
    trigger_update_python_computed_attributes,
)
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.recompute.bulk_write import AttributeValueWrite
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute

PYTHON_ATTRIBUTE_NAME = "pitch"
JINJA2_ATTRIBUTE_NAME = "summary"


def _write(node_id: str, value: Any) -> AttributeValueWrite:
    return AttributeValueWrite(node_id=node_id, field="desc", value=value)


def _node_schema() -> NodeSchema:
    return NodeSchema(
        name="TShirt",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(
                name=JINJA2_ATTRIBUTE_NAME,
                kind="Text",
                optional=True,
                read_only=True,
                computed_attribute=ComputedAttribute(
                    kind=ComputedAttributeKind.JINJA2, jinja2_template="{{ name__value }}"
                ),
            ),
            AttributeSchema(
                name=PYTHON_ATTRIBUTE_NAME,
                kind="Text",
                optional=True,
                read_only=True,
                computed_attribute=ComputedAttribute(
                    kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform="TestingPitch"
                ),
            ),
        ],
    )


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


def test_only_the_named_python_attribute_is_selected() -> None:
    """The flow recomputes the attribute it was given, not every Python attribute of the kind.

    A kind with several of them would otherwise do the work once per attribute per submission.
    """
    selected = _python_transform_attribute(node_schema=_node_schema(), name=PYTHON_ATTRIBUTE_NAME)

    assert selected is not None
    assert selected.transform == "TestingPitch"


@pytest.mark.parametrize("name", [JINJA2_ATTRIBUTE_NAME, "name", "absent"])
def test_a_non_python_or_missing_attribute_is_a_no_op(name: str) -> None:
    """A stale submission finds nothing to do rather than raising: the schema can change under it."""
    assert _python_transform_attribute(node_schema=_node_schema(), name=name) is None


@pytest.mark.parametrize("flow", [process_transform, trigger_update_python_computed_attributes])
def test_the_recompute_origin_is_never_the_default(flow: Any) -> None:
    """A caller that says nothing gets the live origin, so only the coalesced pass drives a chain.

    Three callers pass a list of ids and only one of them is coalesced, so the mode cannot be
    inferred from the arguments. Defaulting the other way would make every live recompute look
    like a chained level.
    """
    parameters = inspect.signature(flow.fn).parameters

    assert parameters["coalesced"].default is False
    assert parameters["recompute_depth"].default == 0
