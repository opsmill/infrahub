from infrahub.git.tasks import format_check_log_entry


def test_format_check_log_entry_message_only() -> None:
    entry = {"level": "ERROR", "message": "boom", "branch": "main"}

    assert format_check_log_entry(entry) == "[ERROR] boom"


def test_format_check_log_entry_with_object_type_and_id() -> None:
    entry = {
        "level": "ERROR",
        "message": "Duplicate serial '12345' for manufacturer 'Acme'.",
        "branch": "main",
        "object_id": "abc-123",
        "object_type": "DcimDeviceAsset",
    }

    assert format_check_log_entry(entry) == (
        "[ERROR] Duplicate serial '12345' for manufacturer 'Acme'. (object_type=DcimDeviceAsset, object_id=abc-123)"
    )


def test_format_check_log_entry_with_object_id_only() -> None:
    entry = {
        "level": "INFO",
        "message": "validated",
        "branch": "main",
        "object_id": "abc-123",
    }

    assert format_check_log_entry(entry) == "[INFO] validated (object_id=abc-123)"


def test_format_check_log_entry_with_object_type_only() -> None:
    entry = {
        "level": "ERROR",
        "message": "missing description",
        "branch": "main",
        "object_type": "TestingCar",
    }

    assert format_check_log_entry(entry) == "[ERROR] missing description (object_type=TestingCar)"


def test_format_check_log_entry_produces_single_line_per_entry() -> None:
    """Regression: the formatter must emit exactly one line per log record."""
    entry = {
        "level": "ERROR",
        "message": "multi word message",
        "branch": "main",
        "object_id": "abc",
        "object_type": "Foo",
    }

    rendered = format_check_log_entry(entry)

    assert "\n" not in rendered
    assert rendered.count("[ERROR]") == 1
