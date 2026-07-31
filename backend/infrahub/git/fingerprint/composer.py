"""Layered composers that turn a definition's output-affecting inputs into a fingerprint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, assert_never

from infrahub.git.closure_builder.post_processing import MANIFEST_PATH
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
    """Return the commit id to fold into a fingerprint, or None to omit it.

    The commit id is folded (making the fingerprint change on every commit, the safe
    over-regenerating default) whenever the definition's inputs cannot be pinned down.

    An incomplete closure always folds the commit id: some output-affecting dependency could
    not be resolved, so hashing only the resolved paths would leave the fingerprint stable
    over an input the system already knows is unknown - an under-regeneration risk.

    A complete closure is trusted differently depending on the builder, expressed through
    `watch_required`:

    - `watch_required=True` (Python transforms, generators): the builder's completeness flag
      is unsound (it only asserts the definition's own package directory was enumerated, so a
      helper imported from outside that directory is silently missed). A present `watch` is
      the only signal trusted to close the set, so the commit id is folded whenever `watch`
      is absent (`None`).
    - `watch_required=False` (Jinja2): completeness comes from a real transitive parse of the
      template include/import/extends graph and is sound. A complete closure alone yields a
      stable, precise fingerprint with no `watch` needed; a dynamic reference drops the flag
      to False, which keeps the commit id folded.
    """
    if not closure_complete:
        return commit
    if watch_required and watch is None:
        return commit
    return None


class ClosurePathSelector:
    """Select the dependency paths that contribute to a fingerprint's hashed closure.

    The manifest is excluded even though it is merged into every definition's stored
    dependencies: its blob changes on any unrelated or comment-only edit, which would churn
    every definition's fingerprint. Its output-affecting fields are folded in separately as
    parsed scalars, so dropping its bytes keeps the fingerprint stable against manifest
    noise while remaining sensitive to the fields that actually matter.
    """

    def __init__(self, *, excluded_paths: frozenset[str]) -> None:
        self._excluded_paths = excluded_paths

    def select(self, dependencies: Iterable[str]) -> list[str]:
        return [path for path in dependencies if path not in self._excluded_paths]


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
        closure_selector: ClosurePathSelector,
        commit: str,
    ) -> None:
        self._hasher = hasher
        self._blob_resolver = blob_resolver
        self._registry = registry
        self._closure_selector = closure_selector
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
                terms.append(f"class_name={inputs.class_name}")
                terms.append(f"convert_query_response={inputs.convert_query_response}")
                watch_required = True
            case Jinja2TransformationFingerprintInput():
                terms.append(f"template_path={inputs.template_path}")
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
        hashed_paths = self._closure_selector.select(dependencies)
        pairs = self._blob_resolver.resolve(hashed_paths)
        return canonical_json([[path, blob_sha] for path, blob_sha in pairs])


def build_fingerprint_composer(*, repo: Repo, commit: str) -> FingerprintComposer:
    """Wire a fingerprint composer for a single import against the pinned commit worktree."""
    return FingerprintComposer(
        hasher=FingerprintHasher(),
        blob_resolver=GitBlobResolver(repo=repo, commit=commit),
        registry=FingerprintRegistry(),
        closure_selector=ClosurePathSelector(excluded_paths=frozenset({MANIFEST_PATH})),
        commit=commit,
    )
