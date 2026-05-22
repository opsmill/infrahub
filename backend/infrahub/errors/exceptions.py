from infrahub.exceptions import ValidationError


class AttributeRequiredError(ValidationError):
    def __init__(self, node_kind: str, field_name: str, message: str | None = None) -> None:
        self.node_kind = node_kind
        self.field_name = field_name
        input_value = message if message is not None else {field_name: "mandatory"}
        super().__init__(input_value)


class AttributeInvalidTypeError(ValidationError):
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
