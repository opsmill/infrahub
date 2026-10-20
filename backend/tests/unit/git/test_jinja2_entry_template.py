import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from infrahub.exceptions import RepositoryConfigurationError
from infrahub.git.jinja2_entry_template import validate_jinja2_entry_template

REPOSITORY_NAME = "my-repository"


@dataclass
class UsableTemplateCase:
    name: str
    template_path: str
    files: dict[str, str] = field(default_factory=dict)


USABLE_TEMPLATE_CASES: list[UsableTemplateCase] = [
    UsableTemplateCase(
        name="template_without_references",
        template_path="templates/report.j2",
        files={"templates/report.j2": "{{ name }}\n"},
    ),
    UsableTemplateCase(
        name="unresolved_include_is_left_to_the_dependency_analysis",
        template_path="templates/report.j2",
        files={"templates/report.j2": '{% include "templates/missing.j2" %}\n'},
    ),
    UsableTemplateCase(
        name="included_template_with_a_syntax_error_is_left_to_the_dependency_analysis",
        template_path="templates/report.j2",
        files={"templates/report.j2": '{% include "templates/broken.j2" %}\n', "templates/broken.j2": "{{ name }\n"},
    ),
    UsableTemplateCase(
        name="leading_slash_names_the_repository_root",
        template_path="/templates/report.j2",
        files={"templates/report.j2": "{{ name }}\n"},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in USABLE_TEMPLATE_CASES])
def test_usable_entry_template_passes(test_case: UsableTemplateCase, tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    for relative_path, content in test_case.files.items():
        (worktree / relative_path).parent.mkdir(parents=True, exist_ok=True)
        (worktree / relative_path).write_text(content, encoding="utf-8")

    validate_jinja2_entry_template(
        identifier=REPOSITORY_NAME, worktree_root=worktree, template_path=test_case.template_path
    )


@dataclass
class UnusableTemplateCase:
    name: str
    template_path: str
    expected_message: str
    files: dict[str, bytes] = field(default_factory=dict)
    outside_files: dict[str, bytes] = field(default_factory=dict)
    """Files written next to the worktree rather than inside it."""


UNUSABLE_TEMPLATE_CASES: list[UnusableTemplateCase] = [
    UnusableTemplateCase(
        name="missing_file",
        template_path="templates/report.j2",
        expected_message="The template file does not exist",
    ),
    UnusableTemplateCase(
        name="path_is_a_directory",
        template_path="templates",
        files={"templates/report.j2": b"{{ name }}\n"},
        expected_message="The template file does not exist",
    ),
    UnusableTemplateCase(
        name="path_is_the_repository_root",
        template_path="/",
        expected_message="The template path does not name a file",
    ),
    UnusableTemplateCase(
        name="empty_file",
        template_path="templates/report.j2",
        files={"templates/report.j2": b""},
        expected_message="The template file is empty",
    ),
    UnusableTemplateCase(
        name="whitespace_only_file",
        template_path="templates/report.j2",
        files={"templates/report.j2": b"  \n\n"},
        expected_message="The template file is empty",
    ),
    UnusableTemplateCase(
        name="file_is_not_utf8_text",
        template_path="templates/report.j2",
        files={"templates/report.j2": b"\xff\xfe{{ name }}\n"},
        expected_message="The template file is not UTF-8 text",
    ),
    UnusableTemplateCase(
        name="syntax_error",
        template_path="templates/report.j2",
        files={"templates/report.j2": b"interface {{ name }}\n{% if enabled %}\n"},
        expected_message=(
            "Syntax error in templates/report.j2, line 2: Unexpected end of template. Jinja was looking for the "
            "following tags: 'elif' or 'else' or 'endif'. The innermost block that needs to be closed is 'if'."
        ),
    ),
    UnusableTemplateCase(
        name="path_outside_the_repository",
        template_path="../outside.j2",
        outside_files={"outside.j2": b"{{ name }}\n"},
        expected_message="The template path is outside the repository",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in UNUSABLE_TEMPLATE_CASES])
def test_unusable_entry_template_is_rejected(test_case: UnusableTemplateCase, tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    for directory, files in ((worktree, test_case.files), (tmp_path, test_case.outside_files)):
        for relative_path, content in files.items():
            (directory / relative_path).parent.mkdir(parents=True, exist_ok=True)
            (directory / relative_path).write_bytes(content)

    with pytest.raises(RepositoryConfigurationError, match=f"^{re.escape(test_case.expected_message)}$"):
        validate_jinja2_entry_template(
            identifier=REPOSITORY_NAME, worktree_root=worktree, template_path=test_case.template_path
        )


def test_symlink_to_a_file_outside_the_repository_is_rejected(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    (worktree / "templates").mkdir(parents=True)
    (tmp_path / "outside.j2").write_text("{{ name }}\n", encoding="utf-8")
    (worktree / "templates" / "report.j2").symlink_to(tmp_path / "outside.j2")

    with pytest.raises(RepositoryConfigurationError, match=r"^The template path is outside the repository$"):
        validate_jinja2_entry_template(
            identifier=REPOSITORY_NAME, worktree_root=worktree, template_path="templates/report.j2"
        )
