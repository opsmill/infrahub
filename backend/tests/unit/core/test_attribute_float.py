import math

import pytest

from infrahub import config
from infrahub.core.attribute import Float
from infrahub.core.schema.attribute_parameters import FloatAttributeParameters
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.exceptions import ValidationError


def _make_schema(
    optional: bool = False,
    parameters: FloatAttributeParameters | None = None,
) -> AttributeSchema:
    return AttributeSchema(
        name="weight",
        kind="Float",
        optional=optional,
        **({"parameters": parameters} if parameters is not None else {}),
    )


# ---------------------------------------------------------------------------
# validate_format - T008 / T009
# ---------------------------------------------------------------------------


class TestFloatValidateFormat:
    """Tests for Float.validate_format covering type acceptance and rejection."""

    def test_float_value_accepted(self) -> None:
        schema = _make_schema()
        Float.validate_format(value=7.7, name="weight", schema=schema)

    def test_integer_coerced_to_float(self) -> None:
        """An int should be silently accepted (coerced to float internally)."""
        schema = _make_schema()
        Float.validate_format(value=8, name="weight", schema=schema)

    def test_zero_float_accepted(self) -> None:
        schema = _make_schema()
        Float.validate_format(value=0.0, name="weight", schema=schema)

    def test_negative_float_accepted(self) -> None:
        schema = _make_schema()
        Float.validate_format(value=-math.pi, name="weight", schema=schema)

    def test_boolean_true_rejected(self) -> None:
        schema = _make_schema()
        with pytest.raises(ValidationError):
            Float.validate_format(value=True, name="weight", schema=schema)

    def test_boolean_false_rejected(self) -> None:
        schema = _make_schema()
        with pytest.raises(ValidationError):
            Float.validate_format(value=False, name="weight", schema=schema)

    def test_string_rejected(self) -> None:
        schema = _make_schema()
        with pytest.raises(ValidationError):
            Float.validate_format(value="7.7", name="weight", schema=schema)

    def test_none_rejected_when_required(self) -> None:
        """None on a required attribute is caught by BaseAttribute.validate (not validate_format),
        but we verify the full flow via the validate classmethod."""
        schema = _make_schema(optional=False)
        with pytest.raises(ValidationError):
            Float.validate(value=None, name="weight", schema=schema)

    def test_none_accepted_when_optional(self) -> None:
        schema = _make_schema(optional=True)
        # validate returns True when value is None and optional is True
        assert Float.validate(value=None, name="weight", schema=schema) is True

    def test_nan_rejected(self) -> None:
        schema = _make_schema()
        with pytest.raises(ValidationError):
            Float.validate_format(value=float("nan"), name="weight", schema=schema)

    def test_positive_infinity_rejected(self) -> None:
        schema = _make_schema()
        with pytest.raises(ValidationError):
            Float.validate_format(value=float("inf"), name="weight", schema=schema)

    def test_negative_infinity_rejected(self) -> None:
        schema = _make_schema()
        with pytest.raises(ValidationError):
            Float.validate_format(value=float("-inf"), name="weight", schema=schema)

    def test_list_rejected(self) -> None:
        schema = _make_schema()
        with pytest.raises(ValidationError):
            Float.validate_format(value=[1.0], name="weight", schema=schema)

    def test_dict_rejected(self) -> None:
        schema = _make_schema()
        with pytest.raises(ValidationError):
            Float.validate_format(value={"v": 1.0}, name="weight", schema=schema)


# ---------------------------------------------------------------------------
# validate_content / FloatAttributeParameters - T012
# ---------------------------------------------------------------------------


class TestFloatValidateContent:
    """Tests for Float.validate_content with FloatAttributeParameters min/max constraints.

    These tests rely on schema_strict_mode being True (the default).
    """

    def test_value_within_range_accepted(self) -> None:
        assert config.SETTINGS.main.schema_strict_mode
        params = FloatAttributeParameters(min_value=0.0, max_value=100.0)
        schema = _make_schema(parameters=params)
        Float.validate_content(value=50.5, name="weight", schema=schema)

    def test_value_below_min_rejected(self) -> None:
        assert config.SETTINGS.main.schema_strict_mode
        params = FloatAttributeParameters(min_value=0.0, max_value=100.0)
        schema = _make_schema(parameters=params)
        with pytest.raises(ValidationError, match="lower than the minimum"):
            Float.validate_content(value=-0.5, name="weight", schema=schema)

    def test_value_above_max_rejected(self) -> None:
        assert config.SETTINGS.main.schema_strict_mode
        params = FloatAttributeParameters(max_value=100.0)
        schema = _make_schema(parameters=params)
        with pytest.raises(ValidationError, match="higher than the maximum"):
            Float.validate_content(value=150.3, name="weight", schema=schema)

    def test_boundary_min_accepted(self) -> None:
        assert config.SETTINGS.main.schema_strict_mode
        params = FloatAttributeParameters(min_value=0.0, max_value=100.0)
        schema = _make_schema(parameters=params)
        Float.validate_content(value=0.0, name="weight", schema=schema)

    def test_boundary_max_accepted(self) -> None:
        assert config.SETTINGS.main.schema_strict_mode
        params = FloatAttributeParameters(min_value=0.0, max_value=100.0)
        schema = _make_schema(parameters=params)
        Float.validate_content(value=100.0, name="weight", schema=schema)

    def test_integer_value_coerced_and_checked(self) -> None:
        """An int value should be coerced to float before parameter validation."""
        assert config.SETTINGS.main.schema_strict_mode
        params = FloatAttributeParameters(min_value=0.0, max_value=100.0)
        schema = _make_schema(parameters=params)
        Float.validate_content(value=50, name="weight", schema=schema)

    def test_integer_value_below_min_rejected(self) -> None:
        assert config.SETTINGS.main.schema_strict_mode
        params = FloatAttributeParameters(min_value=0.0)
        schema = _make_schema(parameters=params)
        with pytest.raises(ValidationError, match="lower than the minimum"):
            Float.validate_content(value=-1, name="weight", schema=schema)

    def test_no_parameters_accepted(self) -> None:
        """When no FloatAttributeParameters are set, any finite float passes."""
        schema = _make_schema()
        Float.validate_content(value=999999.99, name="weight", schema=schema)

    def test_only_min_set(self) -> None:
        assert config.SETTINGS.main.schema_strict_mode
        params = FloatAttributeParameters(min_value=10.0)
        schema = _make_schema(parameters=params)
        Float.validate_content(value=10.0, name="weight", schema=schema)
        Float.validate_content(value=999.9, name="weight", schema=schema)
        with pytest.raises(ValidationError, match="lower than the minimum"):
            Float.validate_content(value=9.99, name="weight", schema=schema)

    def test_only_max_set(self) -> None:
        assert config.SETTINGS.main.schema_strict_mode
        params = FloatAttributeParameters(max_value=50.0)
        schema = _make_schema(parameters=params)
        Float.validate_content(value=50.0, name="weight", schema=schema)
        Float.validate_content(value=-100.0, name="weight", schema=schema)
        with pytest.raises(ValidationError, match="higher than the maximum"):
            Float.validate_content(value=50.01, name="weight", schema=schema)


# ---------------------------------------------------------------------------
# FloatAttributeParameters standalone
# ---------------------------------------------------------------------------


class TestFloatAttributeParameters:
    """Direct tests on FloatAttributeParameters.check_valid_value."""

    def test_check_valid_value_in_range(self) -> None:
        params = FloatAttributeParameters(min_value=-10.0, max_value=10.0)
        params.check_valid_value(value=0.0, name="x")

    def test_check_valid_value_below_min(self) -> None:
        params = FloatAttributeParameters(min_value=0.0, max_value=100.0)
        with pytest.raises(ValidationError, match="lower than the minimum"):
            params.check_valid_value(value=-0.001, name="x")

    def test_check_valid_value_above_max(self) -> None:
        params = FloatAttributeParameters(min_value=0.0, max_value=100.0)
        with pytest.raises(ValidationError, match="higher than the maximum"):
            params.check_valid_value(value=100.001, name="x")

    def test_is_valid_value_true(self) -> None:
        params = FloatAttributeParameters(min_value=0.0, max_value=100.0)
        assert params.is_valid_value(50.0) is True

    def test_is_valid_value_false(self) -> None:
        params = FloatAttributeParameters(min_value=0.0, max_value=100.0)
        assert params.is_valid_value(-1.0) is False

    def test_min_greater_than_max_rejected_in_strict_mode(self) -> None:
        assert config.SETTINGS.main.schema_strict_mode
        with pytest.raises(ValueError, match=r"max_value.*can't be less than.*min_value"):
            FloatAttributeParameters(min_value=100.0, max_value=10.0)
