# Phase 0 Research: SOLID Restructuring of `infrahub.git`

**Feature**: INFP-546 (Epic IFC-2533)
**Branch**: `git-solid-refactor-infp-546`
**Date**: 2026-05-18

This document grounds the implementation plan in the actual state of `backend/infrahub/git/` and resolves every open decision the spec leaves to planning. No NEEDS CLARIFICATION items remain.

## Current state (survey)

### Class hierarchy and sizes

| Class | File | Line | LOC |
|---|---|---|---|
| `InfrahubRepositoryBase` (abstract, Pydantic model) | `backend/infrahub/git/base.py` | 143 | 1161 file |
| `InfrahubRepositoryIntegrator(InfrahubRepositoryBase)` | `backend/infrahub/git/integrator.py` | 146 | 1538 file |
| `InfrahubRepository(InfrahubRepositoryIntegrator)` | `backend/infrahub/git/repository.py` | 26 | 334 file |
| `InfrahubReadOnlyRepository(InfrahubRepositoryIntegrator)` | `backend/infrahub/git/repository.py` | 214 | — |

`integrator.py` is the "1,500-line class" referenced in the spec; `base.py` and `repository.py` are the per-module mypy override targets.

### Workflow-decorated methods on the integrator (Prefect)

Prefect `@flow` / `@task` decorators are fused to business methods. Story 5 splits each into a plain async implementation + a thin decorated wrapper.

**Flows (2):** `import_objects_from_files` (integrator.py:184), `import_all_python_files` (integrator.py:1221).

**Tasks (14):** `import_jinja2_transforms` (241), `import_artifact_definitions` (346), `get_repository_config` (446), `import_schema_files` (513), `import_all_graphql_query` (585), `import_python_check_definitions` (657), `import_generator_definitions` (728), `import_python_transforms` (820), `import_objects` (949), `get_check_definition` (969), `get_python_transforms` (1009), `jinja2_template_render` (1231), `python_check_execute` (1253), `python_transform_execute` (1317). Plus `get_initialized_repo` in `repository.py:315`.

### `import_*` lifecycle (Story 4 surface)

Each of the eight `import_*` methods above owns a compare/create/update lifecycle for one object type (schema, GraphQL query, Python check, generator, Python transform, Jinja2 transform, artifact definition, plus the file-level orchestrator `import_objects`). They share a discover-files → diff-against-graph → reconcile shape.

### Error-pattern conditional chain (FR-005)

`base.py:1083-1115`, static method `_raise_enriched_error_static`: a chain of `if "substring" in error.stderr: raise <Typed>` branches mapping to `RepositoryConnectionError`, `RepositoryInvalidBranchError`, `RepositoryCredentialsError`, `RepositoryError`, with a fallthrough generic raise. Adding a pattern today requires editing the function body.

### Merge return-type contract bug (FR-003)

`repository.py:161` — `async def merge(...) -> bool` returns `False` on the early-exit branch (`commit_after == commit_before`, line 190) and `str(commit_after)` on success (line 197). The declared type lies; call sites must `isinstance`-check.

### Read-only commit-value contract (FR-004)

`base.py:576` — `get_commit_value(branch_name, remote) -> str` is declared abstract. `repository.py:230` — `InfrahubReadOnlyRepository.get_commit_value` shadows it, marks `branch_name` as `# noqa: ARG002`, and **always** performs `git_repo.remotes.origin.fetch()` regardless of the `remote` argument. Same name, two different contracts.

### SDK client and default-branch globals (FR-009, FR-010)

`base.py:183-188` — `@property sdk` lazily mutates `self.client` (a Pydantic-model field) inside the read accessor. `base.py:190-192` — `@property default_branch` falls back to `registry.default_branch` (module-global singleton) when `self.default_branch_name` is `None`.

### Public re-exports (FR-013)

`backend/infrahub/git/__init__.py:1-11` exports `InfrahubReadOnlyRepository`, `InfrahubRepository`, `initialize_repositories_directory`. `repository.py` defines no `__all__`; the symbols imported elsewhere in the backend are the two classes plus `get_initialized_repo` (the `@task`-decorated public function at repository.py:320).

### Type-checker suppressions (FR-018, FR-019)

`pyproject.toml:358-374` — two `[[tool.mypy.overrides]]` blocks. `infrahub.git.base` disables `arg-type, attr-defined, index, return-value`. `infrahub.git.repository` disables `arg-type, assignment, call-overload, return-value`. No explicit override for `infrahub.git.integrator`. The block carries a header comment that the suppressions are temporary. ty has a parallel per-package rule override for `backend/infrahub/git/**` (referenced by the spec, location to confirm during Story 2's first PR).

### Inline `# type: ignore` (FR-019)

27 occurrences across the module, concentrated in `integrator.py` (13 of them). All seen so far are `[call-overload]` and trace to Prefect's task/flow overload signatures — they should disappear naturally as Story 5 moves decorators off business methods.

### Real-remote test fixture (Story 1)

`backend/tests/integration/git/conftest.py:129-202` defines a session-scoped `gogs_server` fixture: a Testcontainer running Gogs with an admin user and token. Helpers `gogs_clone_url` (line 59) and `create_gogs_repo` (line 80) construct authenticated URLs and seed repositories with `.infrahub.yml`. Existing real-remote tests: `test_git_live_remote.py`, `test_delete_git_branch_gogs.py` (covers only the branch-deletion scenario the spec calls out as the lone existing coverage).

### Existing unit tests

`backend/tests/unit/git/`: `test_delete_git_branch.py`, `test_git_repository.py`, `test_transform_python_information.py`. Workflow-engine initialization friction lives here.

## Decisions

### D1 — Module layout for new abstractions

| New artifact | Path | Rationale |
|---|---|---|
| Read-only and full protocols | `backend/infrahub/git/protocols.py` | Sibling to `base.py`/`repository.py`; re-exported from `infrahub.git.repository` for FR-013. |
| Error-pattern registry | `backend/infrahub/git/errors.py` | Pulls the data structure out of `base.py` so registration is module-level. |
| `RepositoryFileImporter` collaborator | `backend/infrahub/git/importer/__init__.py` + one file per object-type handler | Subpackage so per-type handlers (Story 4) land as new files rather than edits to one module. |
| Plain async business implementations (Story 5) | Same file as the wrapper, named with leading underscore | Keeps each unit of work in one place; FR-021 keeps the underscore name private so in-process callers go through the decorated wrapper. |

No top-level rename of `base.py`, `integrator.py`, `repository.py`, `tasks.py`, `models.py`, `utils.py` — FR-013 requires their import paths stay stable.

**Alternatives considered:** putting protocols in `repository.py` directly (rejected — `repository.py` is one of the mypy-suppressed modules, adding to it works against FR-019); putting the importer subpackage under `infrahub.git.integrators/` (rejected — pluralization implies multiple integrators, but the integrator class stays singular).

### D2 — Workflow wrapper split convention (Story 5, FR-008, FR-021)

Each decorated method becomes:

```python
class InfrahubRepositoryIntegrator(...):
    async def _import_schema_files_impl(self, ...) -> ...:
        # plain async logic — no Prefect imports needed at call time
        ...

    @task(name="import-schema-files", ...)
    async def import_schema_files(self, ...) -> ...:
        return await self._import_schema_files_impl(...)
```

The `_impl` method stays on the class (not a free function) so it sees `self`. The decorated method is the public name; in-process callers (including recursive self-calls) go through the wrapper to preserve Prefect retry/checkpointing/telemetry. Unit tests call `_impl` directly — they import the class and invoke the underscored method, no workflow engine initialization required.

**Alternatives considered:** moving the decorated wrapper into `infrahub.git.tasks` and leaving only the plain impl on the class (rejected — public name changes, violates FR-013); making `_impl` a free function (rejected — has to thread `self`-state through arguments, churns call sites).

### D3 — Protocol surface (Story 3, FR-006)

Two `typing.Protocol` types, defined `runtime_checkable=False`:

- `ReadOnlyRepositoryProtocol`: the methods read-only consumers need — `get_commit_value`, `get_worktree`, `find_files`, `get_file_content`, `get_repository_config`, plus the identification fields (`name`, `id`, `default_branch`).
- `RepositoryProtocol(ReadOnlyRepositoryProtocol)`: adds the write surface — `pull`, `push`, `merge`, `rebase`, `sync`, `create_branch`, `delete_branch`, `update_commit_value`.

Exact method set is pinned by a discovery sweep before the protocol-introduction PR lands (FR-020 audit). Both concrete classes (`InfrahubRepository`, `InfrahubReadOnlyRepository`) satisfy `RepositoryProtocol` structurally — the protocols are derived from existing behavior, not new.

**Alternatives considered:** one protocol with optional methods (rejected — defeats the read-only/full distinction Story 3 is built around); abstract base classes (rejected — Pydantic-model inheritance plus ABCs has been a source of mypy noise here already).

### D4 — `RepositoryFileImporter` shape (Story 4, FR-007)

```python
class RepositoryFileImporter:
    def __init__(self, repository: RepositoryProtocol) -> None: ...
    def register(self, handler: FileImportHandler) -> None: ...
    async def import_all(self, *, infrahub_branch_name: str, commit: str) -> None: ...

class FileImportHandler(Protocol):
    name: str
    async def discover(self, repository: RepositoryProtocol, commit: str) -> Iterable[ObjectFile]: ...
    async def reconcile(self, repository: RepositoryProtocol, files: Iterable[ObjectFile], ...) -> None: ...
```

Per-type handlers (`SchemaFileHandler`, `GraphqlQueryHandler`, `PythonCheckHandler`, `GeneratorHandler`, `PythonTransformHandler`, `Jinja2TransformHandler`, `ArtifactDefinitionHandler`) live in `backend/infrahub/git/importer/<type>.py`. The integrator instantiates the importer in its constructor and pre-registers the built-in handlers. The eight `import_*` methods on the integrator become one-line delegates to the importer (FR-016).

**Alternatives considered:** flat registry as a module-level list (rejected — couples handler registration to import order); a separate per-object-type strategy class without a shared protocol (rejected — gives no extension seam to the OCP improvement Story 4 is buying).

### D5 — Error-pattern registry shape (Story 2, FR-005)

```python
@dataclass(frozen=True, slots=True)
class ErrorRule:
    matcher: Callable[[str], bool]                                    # accepts error.stderr
    factory: Callable[[ErrorContext, GitCommandError], Exception]

# Named module-level builders — one per exception shape, reused across rules.
def _connection_error(ctx: ErrorContext, _exc: GitCommandError) -> Exception:
    return RepositoryConnectionError(identifier=ctx.name)
# ... _credentials_error, _invalid_branch_error, _merge_repository_error ...

ERROR_RULES: tuple[ErrorRule, ...] = (
    ErrorRule(any_substring("Repository not found",
                            "does not appear to be a git",
                            "Failed to connect to"),  _connection_error),
    ...
)
```

Ordered tuple, first match wins, matches the existing top-to-bottom semantics of the conditional chain. The fallthrough `RepositoryError(identifier=..., message=stderr)` remains the loop's else clause. Adding a new pattern is one `ErrorRule(...)` line when the builder already exists, or one builder + one rule when it doesn't — no edit to `raise_enriched`'s body. Named builders avoid anonymous-lambda registries (they are searchable, independently testable, and de-duplicate the three `if`-branches that today produce `RepositoryConnectionError`).

**Alternatives considered:** regex-only matchers (rejected — current code uses plain substring matching and case-insensitive checks both; a `Callable[[str], bool]` matcher is more honest than forcing every check into a regex); a `dict[str, type[Exception]]` keyed by pattern (rejected — loses order, can't express "raise X with these constructor args from this matcher"); inline `lambda` factories on each rule (rejected — anonymous, not searchable, and duplicates the same exception construction across multiple rules); declarative `use_branch: bool` / `use_location: bool` flags on `ErrorRule` (rejected — pushes per-exception-shape knowledge into `raise_enriched`'s body via `**kwargs: Any`); a `from_context` classmethod on each exception (rejected — modifies shared exception classes used elsewhere in the backend, which raises FR-014 risk for what is supposed to be pure restructuring).

### D6 — Read-only `get_commit_value` (FR-004)

Out-of-Scope permits renaming *provided the abstract contract on the base class is not broken*. Decision: keep the name `get_commit_value` on both classes (it is the abstract method), tighten the read-only override with an explicit docstring stating "always fetches from origin and returns the resolved commit; the `branch_name` argument is preserved for interface compatibility and is ignored". Add a unit test that asserts `origin.fetch` is called once per invocation (FR-004 acceptance). Renaming would require a follow-up that touches every caller — out of scope per the spec.

**Alternatives considered:** rename to `get_latest_remote_commit` and adjust the abstract method to be a union of behaviors (rejected — widens the abstract contract, breaks FR-004's "do not break the abstract contract" constraint); add a `network: bool` flag on the base signature (rejected — behavior change, not a contract clarification).

### D7 — Merge return type (FR-003)

The runtime returns either `False` (line 190) or `str(commit_after)` (line 197). The honest declaration is `Literal[False] | str`. The PR is annotation-only: `-> str | Literal[False]`, with `from typing import Literal` added. Call sites already test for truthiness or `isinstance(result, str)`; no caller change is needed in the same PR (FR-014). SC-006 follow-up may remove the now-redundant checks separately.

**Alternatives considered:** change the runtime to return `""` on the early-exit (rejected — behavior change, violates FR-014); use `Optional[str]` and return `None` (rejected — same behavior change problem); introduce a small result class (rejected — adds an abstraction with one caller, against simplicity principle VII).

### D8 — Test placement

- New integration scenarios for Story 1 → `backend/tests/integration/git/`, one file per scenario family (`test_auth_and_access.py`, `test_push_failures.py`, `test_merge_scenarios.py`, etc.). Reuses `gogs_server` and `create_gogs_repo` as-is — no fixture extension in scope.
- New unit tests for Story 5 → `backend/tests/unit/git/`, one file per method or per `import_*` lifecycle (`test_import_schema_files_unit.py`). These exercise the `_impl` methods directly.
- Story 2's merge-annotation PR ships with a typing assertion (`reveal_type` test via pytest is fragile — use mypy assertion in a fixture or rely on the existing type-check CI step).
- Story 2's commit-value pinning test → `backend/tests/integration/git/test_readonly_get_commit_value.py`. The mock-call-count assertion uses `unittest.mock.patch` on `git_repo.remotes.origin.fetch` — FR-020 marks this as a "stable seam" (the seam isn't being moved by this work).

### D9 — Suppression removal cadence (FR-018, FR-019)

Every PR that completes a story is accompanied by a check: "did this PR make a `# type: ignore` removable, or a mypy override entry narrowable?" If yes, remove in the same PR. Concrete expectations:

- Story 5 (workflow split) likely removes most of the 13 `[call-overload]` ignores in `integrator.py` because the decorated wrapper is no longer the thing being typed for caller use.
- Story 3 (protocols) likely removes some `attr-defined` entries from `infrahub.git.base` once consumers depend on the protocol surface.
- Story 4 (importer extraction) does not aim to remove suppressions directly, but it shrinks the file that the override covers, which makes the next focused-removal PR easier.

The union invariant is checked by running `git diff pyproject.toml` and grepping for new `# type: ignore` per PR.

### D10 — Branch name and merge target

Branch: `git-solid-refactor-infp-546` (matches the spec). Merge target: `develop` for every PR in this work. No long-lived integration branch.

## Open items intentionally left to story PRs

- Exact ty rule list to narrow per-PR (the spec references it; the precise list is read from `pyproject.toml` when the first Story 2 PR is opened).
- The 244-byte branch-name cap is not relevant — `git-solid-refactor-infp-546` is well under.
- Towncrier fragment is produced once at the close of all stories (per spec Assumptions).
