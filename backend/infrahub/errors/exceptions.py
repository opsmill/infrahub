from typing import ClassVar

from infrahub.exceptions import ValidationError


class AttributeRequiredError(ValidationError):
    CATALOGUE_CODE: ClassVar[str] = "ATTRIBUTE_REQUIRED"

    def __init__(self, node_kind: str, field_name: str, message: str | None = None) -> None:
        self.node_kind = node_kind
        self.field_name = field_name
        input_value = message if message is not None else {field_name: "mandatory"}
        super().__init__(input_value)


class AttributeInvalidTypeError(ValidationError):
    CATALOGUE_CODE: ClassVar[str] = "ATTRIBUTE_INVALID_TYPE"

    def __init__(
        self,
        node_kind: str,
        field_name: str,
        expected_type: str,
        received_type: str,
        message: str | None = None,
    ) -> None:
        self.node_kind = node_kind
        self.field_name = field_name
        self.expected_type = expected_type
        self.received_type = received_type
        input_value = (
            message if message is not None else {field_name: f"{received_type} is not a valid {expected_type}"}
        )
        super().__init__(input_value)


class AttributeConstraintViolationError(ValidationError):
    CATALOGUE_CODE: ClassVar[str] = "ATTRIBUTE_CONSTRAINT_VIOLATION"

    def __init__(
        self,
        node_kind: str,
        field_name: str,
        constraint: str,
        detail: str | None = None,
        message: str | None = None,
    ) -> None:
        self.node_kind = node_kind
        self.field_name = field_name
        self.constraint = constraint
        self.detail = detail
        if message is not None:
            input_value: str | dict[str, str] = message
        else:
            reason = f"{constraint}" if detail is None else f"{constraint}: {detail}"
            input_value = {field_name: reason}
        super().__init__(input_value)
