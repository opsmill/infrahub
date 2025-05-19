from enum import Enum


class ConstraintIdentifier(str, Enum):
    ATTRIBUTE_PARAMETERS_REGEX_UPDATE = "attribute.parameters.regex.update"
    ATTRIBUTE_PARAMETERS_MIN_LENGTH_UPDATE = "attribute.parameters.min_length.update"
    ATTRIBUTE_PARAMETERS_MAX_LENGTH_UPDATE = "attribute.parameters.max_length.update"
