from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import TemplateNotFound

from infrahub.git.closure_builder.canonicalizer import canonicalize_path
from infrahub.git.closure_builder.result import UnresolvedRef

if TYPE_CHECKING:
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader


class Jinja2ReferenceResolver:
    """Validate a single Jinja2 reference and turn it into a canonical worktree-relative path.

    Returns either the canonical path (the reference is usable as a closure
    entry) or an `UnresolvedRef` describing why the reference cannot be
    followed: dynamic, non-canonicalizable, escaping the worktree, or missing
    from the loader's view.
    """

    def resolve(
        self,
        *,
        reference: str | None,
        current: str,
        worktree_root: Path,
        worktree_real: Path,
        loader: FileSystemLoader,
        env: Environment,
    ) -> str | UnresolvedRef:
        if reference is None:
            return UnresolvedRef(file=current, location="dynamic include/import/extends")

        try:
            canonical = canonicalize_path(reference)
        except ValueError:
            return UnresolvedRef(file=current, location=f"unresolvable reference: {reference!r}")

        resolved_real = (worktree_root / canonical).resolve()
        if resolved_real != worktree_real and not resolved_real.is_relative_to(worktree_real):
            return UnresolvedRef(file=current, location=f"reference escapes worktree: {reference!r}")

        try:
            loader.get_source(env, canonical)
        except TemplateNotFound:
            return UnresolvedRef(file=current, location=f"missing template: {canonical}")

        return canonical
