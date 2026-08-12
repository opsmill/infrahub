from __future__ import annotations

from dataclasses import dataclass

from infrahub.git.closure_builder.canonicalizer import canonicalize_path


@dataclass(frozen=True, kw_only=True, slots=True)
class UnresolvedRef:
    file: str
    location: str


@dataclass(frozen=True, kw_only=True, slots=True)
class ClosureResult:
    dependencies: tuple[str, ...]
    complete: bool
    unresolved: tuple[UnresolvedRef, ...]

    def __post_init__(self) -> None:
        previous: str | None = None
        for entry in self.dependencies:
            if canonicalize_path(entry) != entry:
                raise ValueError(
                    f"dependency {entry!r} is not in canonical form; "
                    f"every entry must satisfy canonicalize_path(p) == p before persistence"
                )
            if previous is not None:
                if entry == previous:
                    raise ValueError(f"duplicate dependency entry: {entry!r}")
                if entry < previous:
                    raise ValueError(
                        f"dependencies must be sorted lexicographically; got {previous!r} before {entry!r}"
                    )
            previous = entry
