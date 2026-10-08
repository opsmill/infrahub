from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import Environment, TemplateSyntaxError

from infrahub.exceptions import RepositoryConfigurationError
from infrahub.git.closure_builder.canonicalizer import InvalidDependencyPathError, canonicalize_path

if TYPE_CHECKING:
    from pathlib import Path


def validate_jinja2_entry_template(identifier: str, worktree_root: Path, template_path: str) -> None:
    """Check that the entry template of a Jinja2 transform is a non-empty file in the repository that parses.

    Raises:
        RepositoryConfigurationError: When the template is outside the repository, does not exist, is empty,
            is not UTF-8 text, or has a syntax error.

    """
    try:
        relative_path = canonicalize_path(template_path)
    except InvalidDependencyPathError as exc:
        raise RepositoryConfigurationError(
            identifier=identifier, message="The template path does not name a file"
        ) from exc

    entry_path = worktree_root / relative_path
    if not entry_path.resolve().is_relative_to(worktree_root.resolve()):
        raise RepositoryConfigurationError(identifier=identifier, message="The template path is outside the repository")
    if not entry_path.is_file():
        raise RepositoryConfigurationError(identifier=identifier, message="The template file does not exist")

    try:
        source = entry_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise RepositoryConfigurationError(
            identifier=identifier, message="The template file is not UTF-8 text"
        ) from exc
    if not source.strip():
        raise RepositoryConfigurationError(identifier=identifier, message="The template file is empty")

    try:
        Environment(autoescape=True).parse(source=source, name=relative_path)
    except TemplateSyntaxError as exc:
        raise RepositoryConfigurationError(
            identifier=identifier, message=f"Syntax error in {relative_path}, line {exc.lineno}: {exc.message}"
        ) from exc
