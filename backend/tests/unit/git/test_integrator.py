from dataclasses import dataclass, field
from pathlib import Path

import pytest
from infrahub_sdk.yaml import SchemaFile

from infrahub.git.integrator import find_unloadable_schema_files, format_unloadable_schema_files


def build_schema_file(
    identifier: str,
    content: dict | None = None,
    valid: bool = True,
    error_message: str | None = None,
) -> SchemaFile:
    return SchemaFile(
        identifier=identifier,
        location=Path(identifier),
        content=content,
        valid=valid,
        error_message=error_message,
    )


@dataclass
class FindUnloadableTestCase:
    name: str
    """Descriptive name for the test scenario (used as test ID)."""

    schemas_data: list[SchemaFile]
    """The schema files as the loader left them."""

    expected_identifiers: list[str] = field(default_factory=list)
    """Identifiers of the files expected to be reported as unloadable, in order."""


FIND_UNLOADABLE_TEST_CASES: list[FindUnloadableTestCase] = [
    FindUnloadableTestCase(
        name="every_file_loaded_reports_nothing",
        schemas_data=[
            build_schema_file(identifier="one.yml", content={"version": "1.0"}),
            build_schema_file(identifier="two.yml", content={"version": "1.0"}),
        ],
    ),
    FindUnloadableTestCase(
        name="absent_content_is_unloadable",
        schemas_data=[
            build_schema_file(identifier="one.yml", content={"version": "1.0"}),
            build_schema_file(identifier="broken.yml", valid=False, error_message="Invalid YAML/JSON file"),
        ],
        expected_identifiers=["broken.yml"],
    ),
    FindUnloadableTestCase(
        name="empty_document_is_unloadable_even_though_content_is_a_dict",
        schemas_data=[
            build_schema_file(identifier="empty.yml", content={}, valid=False, error_message="Empty YAML/JSON file"),
        ],
        expected_identifiers=["empty.yml"],
    ),
    FindUnloadableTestCase(
        name="every_unloadable_file_is_reported_not_only_the_first",
        schemas_data=[
            build_schema_file(identifier="first.yml", valid=False, error_message="Empty YAML/JSON file"),
            build_schema_file(identifier="ok.yml", content={"version": "1.0"}),
            build_schema_file(identifier="second.yml", valid=False, error_message="Invalid YAML/JSON file"),
        ],
        expected_identifiers=["first.yml", "second.yml"],
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in FIND_UNLOADABLE_TEST_CASES],
)
def test_find_unloadable_schema_files(test_case: FindUnloadableTestCase) -> None:
    """A file is unloadable when the loader flagged it or left no content behind."""
    unloadable = find_unloadable_schema_files(schemas_data=test_case.schemas_data)

    assert [item.identifier for item in unloadable] == test_case.expected_identifiers


@dataclass
class FormatUnloadableTestCase:
    name: str
    """Descriptive name for the test scenario (used as test ID)."""

    unloadable: list[SchemaFile]
    """The files reported as unloadable."""

    expected: str
    """The full message handed to the caller."""


FORMAT_UNLOADABLE_TEST_CASES: list[FormatUnloadableTestCase] = [
    FormatUnloadableTestCase(
        name="single_file_carries_the_loader_reason",
        unloadable=[build_schema_file(identifier="empty.yml", valid=False, error_message="Empty YAML/JSON file")],
        expected="Unable to load 1 schema file(s): empty.yml (Empty YAML/JSON file)",
    ),
    FormatUnloadableTestCase(
        name="every_file_is_named",
        unloadable=[
            build_schema_file(identifier="empty.yml", valid=False, error_message="Empty YAML/JSON file"),
            build_schema_file(identifier="broken.yml", valid=False, error_message="Invalid YAML/JSON file"),
        ],
        expected=(
            "Unable to load 2 schema file(s): empty.yml (Empty YAML/JSON file), broken.yml (Invalid YAML/JSON file)"
        ),
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in FORMAT_UNLOADABLE_TEST_CASES],
)
def test_format_unloadable_schema_files(test_case: FormatUnloadableTestCase) -> None:
    """The reported message names every file and the reason the loader recorded for it."""
    assert format_unloadable_schema_files(unloadable=test_case.unloadable) == test_case.expected
