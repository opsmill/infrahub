from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from infrahub_sdk.schema.repository import InfrahubJinja2TransformConfig
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, meta

from infrahub.git.closure_builder.canonicalizer import canonicalize_path
from infrahub.git.closure_builder.result import ClosureResult, UnresolvedRef

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.git.closure_builder.jinja2_reference_resolver import Jinja2ReferenceResolver
    from infrahub.git.closure_builder.protocols import TransformConfig


class Jinja2Closure:
    """Walk the static include/import/extends graph of a Jinja2 template.

    Parses each reached template, collects referenced templates via
    ``jinja2.meta.find_referenced_templates``, and walks transitively. Each
    individual reference is handed to a `Jinja2ReferenceResolver` which decides
    whether the reference can be enqueued or must be recorded as unresolved.

    The returned `ClosureResult` is sorted, canonicalized, and deduplicated.
    """

    def __init__(self, reference_resolver: Jinja2ReferenceResolver) -> None:
        self._reference_resolver = reference_resolver

    def supports(self, transform_config: TransformConfig) -> bool:
        return isinstance(transform_config, InfrahubJinja2TransformConfig)

    def build(
        self,
        transform_config: InfrahubJinja2TransformConfig,
        worktree_root: Path,
    ) -> ClosureResult:
        loader = FileSystemLoader(str(worktree_root))
        env = Environment(loader=loader, autoescape=True)
        worktree_real = worktree_root.resolve()

        entry_path = canonicalize_path(str(transform_config.template_path))

        entry_real = (worktree_root / entry_path).resolve()
        if entry_real != worktree_real and not entry_real.is_relative_to(worktree_real):
            return ClosureResult(
                dependencies=(),
                complete=False,
                unresolved=(UnresolvedRef(file=entry_path, location="entry path escapes worktree"),),
            )

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
                resolved = self._reference_resolver.resolve(
                    reference=reference,
                    current=current,
                    worktree_root=worktree_root,
                    worktree_real=worktree_real,
                    loader=loader,
                    env=env,
                )
                if isinstance(resolved, UnresolvedRef):
                    complete = False
                    unresolved.append(resolved)
                    continue

                if resolved not in visited:
                    queue.append(resolved)

        return ClosureResult(
            dependencies=tuple(sorted(visited)),
            complete=complete,
            unresolved=tuple(unresolved),
        )
