from enum import Enum


class ConstraintIdentifier(str, Enum):
    ATTRIBUTE_PARAMETERS_REGEX_UPDATE = "attribute.parameters.regex.update"
    ATTRIBUTE_PARAMETERS_MIN_LENGTH_UPDATE = "attribute.parameters.min_length.update"
    ATTRIBUTE_PARAMETERS_MAX_LENGTH_UPDATE = "attribute.parameters.max_length.update"
    ATTRIBUTE_PARAMETERS_MIN_VALUE_UPDATE = "attribute.parameters.min_value.update"
    ATTRIBUTE_PARAMETERS_MAX_VALUE_UPDATE = "attribute.parameters.max_value.update"
    ATTRIBUTE_PARAMETERS_EXCLUDED_VALUES_UPDATE = "attribute.parameters.excluded_values.update"
    ATTRIBUTE_PARAMETERS_END_RANGE_UPDATE = "attribute.parameters.end_range.update"
    ATTRIBUTE_PARAMETERS_START_RANGE_UPDATE = "attribute.parameters.start_range.update"
