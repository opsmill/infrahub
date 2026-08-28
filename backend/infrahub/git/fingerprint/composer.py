"""Layered composers that turn a definition's output-affecting inputs into a fingerprint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, assert_never

from infrahub.git.fingerprint.blob_resolver import GitBlobResolver
from infrahub.git.fingerprint.hasher import FingerprintHasher, canonical_json
from infrahub.git.fingerprint.registry import FingerprintKind, FingerprintRegistry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from git import Repo
    from infrahub_sdk.schema.repository import InfrahubWatchConfig

    from infrahub.git.fingerprint.blob_resolver import BlobResolver


def fold_commit_id(
    *, commit: str, watch: InfrahubWatchConfig | None, closure_complete: bool, watch_required: bool
) -> str | None:
    """Return the commit id to mix into a fingerprint, or None to leave it out.

    Mixing the commit id in makes the fingerprint change on every commit: the definition is
    regenerated more often than it needs to be, but a change is never missed. Leaving it out
    makes the fingerprint change only when one of the listed dependencies changes. So the
    commit id goes in whenever we cannot be sure the dependency list names every file that
    affects the definition's output.

    `closure_complete=False` means the dependency scan gave up on at least one reference, so
    the system already knows a file is missing from the list. The commit id always goes in.

    When the list is complete, how far that can be trusted depends on how it was built, which
    the caller states through `watch_required`:

    - `watch_required=True` - the list names the entry point only, with no dependency scan
      behind it. "Complete" merely means the entry point was resolved, so a helper the source
      imports is missing from the list without anything noticing. Only a `watch` declaration,
      where the author names the extra files by hand, is trusted to close the list; without
      one the commit id goes in.
    - `watch_required=False` - the list was built by parsing the source and following every
      reference it declares, and any reference that could not be followed already set
      `closure_complete=False`. A complete list is therefore trustworthy by itself, and no
      `watch` declaration is needed to leave the commit id out.
    """
    if not closure_complete:
        return commit
    if watch_required and watch is None:
        return commit
    return None


@dataclass(frozen=True, kw_only=True)
class QueryFingerprintInput:
    name: str
    query_text: str


@dataclass(frozen=True, kw_only=True)
class PythonTransformationFingerprintInput:
    name: str
    query_name: str
    dependencies: tuple[str, ...]
    dependencies_complete: bool
    watch: InfrahubWatchConfig | None
    file_path: str
    class_name: str
    convert_query_response: bool


@dataclass(frozen=True, kw_only=True)
class Jinja2TransformationFingerprintInput:
    name: str
    query_name: str
    dependencies: tuple[str, ...]
    dependencies_complete: bool
    watch: InfrahubWatchConfig | None
    template_path: str


@dataclass(frozen=True, kw_only=True)
class ArtifactDefinitionFingerprintInput:
    name: str
    transformation_name: str
    parameters: dict[str, Any]
    content_type: str
    artifact_name: str | None
    target_group_id: str | None


@dataclass(frozen=True, kw_only=True)
class GeneratorDefinitionFingerprintInput:
    name: str
    query_name: str
    dependencies: tuple[str, ...]
    dependencies_complete: bool
    watch: InfrahubWatchConfig | None
    parameters: dict[str, Any]
    file_path: str
    class_name: str
    convert_query_response: bool
    target_group_id: str | None


class FingerprintComposer:
    """Compose the fingerprint for each definition kind from its output-affecting inputs.

    Every entry method both returns the digest and records it in the registry, so a
    higher layer within the same import reads the freshly-computed value.
    """

    def __init__(
        self,
        *,
        hasher: FingerprintHasher,
        blob_resolver: BlobResolver,
        registry: FingerprintRegistry,
        commit: str,
    ) -> None:
        self._hasher = hasher
        self._blob_resolver = blob_resolver
        self._registry = registry
        self._commit = commit

    @property
    def registry(self) -> FingerprintRegistry:
        return self._registry

    def compose_query(self, inputs: QueryFingerprintInput) -> str:
        fingerprint = self._hasher.hash([f"query_text={inputs.query_text}"])
        self._registry.register(kind=FingerprintKind.QUERY, name=inputs.name, fingerprint=fingerprint)
        return fingerprint

    def compose_transformation(
        self, inputs: PythonTransformationFingerprintInput | Jinja2TransformationFingerprintInput
    ) -> str:
        query_fingerprint = self._registry.get(kind=FingerprintKind.QUERY, name=inputs.query_name)
        terms = [
            f"query_fingerprint={query_fingerprint or ''}",
            f"closure={self._closure_term(inputs.dependencies)}",
        ]
        match inputs:
            case PythonTransformationFingerprintInput():
                # The closure is a sorted set of paths, so it cannot say which of them is the
                # entry point: when `watch` names a directory, moving the entry point to another
                # file already in that directory leaves the closure identical.
                terms.append(f"file_path={inputs.file_path}")
                terms.append(f"class_name={inputs.class_name}")
                terms.append(f"convert_query_response={inputs.convert_query_response}")
                # A Python transform's dependencies are auto-detected as its source file alone,
                # so anything it imports is absent from the list: the author has to name those
                # files in `watch` before the fingerprint can drop the commit id.
                watch_required = True
            case Jinja2TransformationFingerprintInput():
                terms.append(f"template_path={inputs.template_path}")
                # A Jinja2 transform's dependencies come from parsing the template and following
                # every include/import/extends it declares, so a complete list already names
                # every file that affects the rendered output.
                watch_required = False
            case _:  # pragma: no cover - exhaustiveness guard for a new transform kind
                assert_never(inputs)

        commit_term = self._resolve_commit_term(
            watch=inputs.watch,
            closure_complete=inputs.dependencies_complete,
            upstream_resolved=query_fingerprint is not None,
            watch_required=watch_required,
        )
        if commit_term is not None:
            terms.append(f"commit_id={commit_term}")

        fingerprint = self._hasher.hash(terms)
        self._registry.register(kind=FingerprintKind.TRANSFORMATION, name=inputs.name, fingerprint=fingerprint)
        return fingerprint

    def compose_artifact_definition(self, inputs: ArtifactDefinitionFingerprintInput) -> str:
        transformation_fingerprint = (
            self._registry.get(kind=FingerprintKind.TRANSFORMATION, name=inputs.transformation_name) or ""
        )
        terms = [
            f"transformation_fingerprint={transformation_fingerprint}",
            f"parameters={canonical_json(inputs.parameters)}",
            f"content_type={inputs.content_type}",
            f"artifact_name={inputs.artifact_name}",
            f"target_group_id={inputs.target_group_id}",
        ]
        fingerprint = self._hasher.hash(terms)
        self._registry.register(kind=FingerprintKind.ARTIFACT_DEFINITION, name=inputs.name, fingerprint=fingerprint)
        return fingerprint

    def compose_generator_definition(self, inputs: GeneratorDefinitionFingerprintInput) -> str:
        query_fingerprint = self._registry.get(kind=FingerprintKind.QUERY, name=inputs.query_name)
        terms = [
            f"query_fingerprint={query_fingerprint or ''}",
            f"closure={self._closure_term(inputs.dependencies)}",
            f"parameters={canonical_json(inputs.parameters)}",
            f"file_path={inputs.file_path}",
            f"class_name={inputs.class_name}",
            f"convert_query_response={inputs.convert_query_response}",
            f"target_group_id={inputs.target_group_id}",
        ]
        commit_term = self._resolve_commit_term(
            watch=inputs.watch,
            closure_complete=inputs.dependencies_complete,
            upstream_resolved=query_fingerprint is not None,
            watch_required=True,
        )
        if commit_term is not None:
            terms.append(f"commit_id={commit_term}")

        fingerprint = self._hasher.hash(terms)
        self._registry.register(kind=FingerprintKind.GENERATOR_DEFINITION, name=inputs.name, fingerprint=fingerprint)
        return fingerprint

    def _resolve_commit_term(
        self,
        *,
        watch: InfrahubWatchConfig | None,
        closure_complete: bool,
        upstream_resolved: bool,
        watch_required: bool,
    ) -> str | None:
        """Return the commit-id term for a transform/generator, or None to omit it.

        A referenced upstream fingerprint that is absent from the same-import registry is an
        unresolved output-affecting input, so it is treated exactly like an incomplete closure:
        the commit id is folded in and the fingerprint can never be stable over an upstream it
        could not read.
        """
        return fold_commit_id(
            commit=self._commit,
            watch=watch,
            closure_complete=closure_complete and upstream_resolved,
            watch_required=watch_required,
        )

    def _closure_term(self, dependencies: Iterable[str]) -> str:
        pairs = self._blob_resolver.resolve(list(dependencies))
        return canonical_json([[path, blob_sha] for path, blob_sha in pairs])


def build_fingerprint_composer(*, repo: Repo, commit: str) -> FingerprintComposer:
    """Wire a fingerprint composer for a single import against the pinned commit worktree."""
    return FingerprintComposer(
        hasher=FingerprintHasher(),
        blob_resolver=GitBlobResolver(repo=repo, commit=commit),
        registry=FingerprintRegistry(),
        commit=commit,
    )
