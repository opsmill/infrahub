from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError, meta

from infrahub.git.closure_builder.canonicalizer import canonicalize_path
from infrahub.git.closure_builder.result import ClosureResult, UnresolvedRef

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk.schema.repository import InfrahubJinja2TransformConfig


class Jinja2Closure:
    """Compute the static include/import/extends closure of a Jinja2 template.

    Parses each reached template, collects referenced templates via
    ``jinja2.meta.find_referenced_templates``, and walks transitively. Dynamic
    references, missing files, and references that escape the worktree root are
    each recorded as `UnresolvedRef` and mark the closure incomplete; the walk
    continues so a single import pass surfaces every problem.

    The returned `ClosureResult` is sorted, canonicalized, and deduplicated.
    """

    def build(
        self,
        transform_config: InfrahubJinja2TransformConfig,
        worktree_root: Path,
    ) -> ClosureResult:
        loader = FileSystemLoader(str(worktree_root))
        env = Environment(loader=loader, autoescape=True)
        worktree_real = worktree_root.resolve()

        entry_path = canonicalize_path(str(transform_config.template_path))

        visited: set[str] = set()
        unresolved: list[UnresolvedRef] = []
        queue: deque[str] = deque([entry_path])
        complete = True

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            source_path = worktree_root / current
            try:
                source = source_path.read_text(encoding="utf-8")
            except OSError:
                complete = False
                unresolved.append(UnresolvedRef(file=current, location="template not readable"))
                continue

            try:
                ast = env.parse(source=source, name=current, filename=str(source_path))
            except TemplateSyntaxError:
                complete = False
                unresolved.append(UnresolvedRef(file=current, location="template syntax error"))
                continue

            for reference in meta.find_referenced_templates(ast):
                if reference is None:
                    complete = False
                    unresolved.append(UnresolvedRef(file=current, location="dynamic include/import/extends"))
                    continue

                try:
                    canonical = canonicalize_path(reference)
                except ValueError:
                    complete = False
                    unresolved.append(UnresolvedRef(file=current, location=f"unresolvable reference: {reference!r}"))
                    continue

                resolved_real = (worktree_root / canonical).resolve()
                if resolved_real != worktree_real and not resolved_real.is_relative_to(worktree_real):
                    complete = False
                    unresolved.append(
                        UnresolvedRef(file=current, location=f"reference escapes worktree: {reference!r}")
                    )
                    continue

                try:
                    loader.get_source(env, canonical)
                except TemplateNotFound:
                    complete = False
                    unresolved.append(UnresolvedRef(file=current, location=f"missing template: {canonical}"))
                    continue

                if canonical not in visited:
                    queue.append(canonical)

        dependencies = tuple(sorted(visited))
        return ClosureResult(
            dependencies=dependencies,
            complete=complete,
            unresolved=tuple(unresolved),
        )
