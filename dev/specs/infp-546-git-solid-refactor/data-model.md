# Phase 1 Data Model: SOLID Restructuring of `infrahub.git`

**Note:** This is a structural refactor. No database schema, no Pydantic API model, and no persisted-data shape changes. "Data model" here documents the new code-structure entities the refactor introduces — protocols, the importer collaborator, the error-pattern registry, and the workflow split convention — so contracts/, tasks.md, and reviewers share one vocabulary.

---

## 1. Repository protocols

Two `typing.Protocol` types in `backend/infrahub/git/protocols.py`, re-exported from `infrahub.git.repository` so existing imports keep working.

### `ReadOnlyRepositoryProtocol`

Surface for consumers that only read files at a commit. The exact method set is fixed by an FR-020 audit before the protocol PR lands; the working list is:

| Member | Kind | Source on concrete classes |
|---|---|---|
| `name: str` | attribute | Pydantic field on `InfrahubRepositoryBase` |
| `id: str` | attribute | Pydantic field on `InfrahubRepositoryBase` |
| `default_branch: str` | attribute (property) | `base.py:190` |
| `get_commit_value(branch_name: str, remote: bool = False) -> str` | method | `base.py:576` abstract; impls on both subclasses |
| `get_commit_worktree(commit: str) -> Worktree` | method | `base.py:461` |
| `get_worktree(...) -> Worktree` | method | `base.py:447` |
| `find_files(...) -> list[Path]` | method | `base.py:1003` |
| `get_file_content(...) -> str` | method | (located during audit) |
| `get_repository_config(...) -> InfrahubRepositoryConfig` | method | `integrator.py:446` |

`Protocol` body uses `...` for every member. No runtime checking (`runtime_checkable=False`).

### `RepositoryProtocol(ReadOnlyRepositoryProtocol)`

Adds the write surface. Working list:

| Member | Source |
|---|---|
| `pull(branch_name: str, ...) -> ...` | `base.py` |
| `push(branch_name: str) -> bool` | `repository.py:144` (write-only class) |
| `merge(source_branch: str, dest_branch: str, push_remote: bool = True) -> str \| Literal[False]` | `repository.py:161` (with the Story 2 annotation fix) |
| `rebase(branch_name: str, source_branch: str, push_remote: bool = True) -> bool` | `repository.py:199` |
| `sync(...) -> ...` | `base.py` |
| `create_branch_in_git(...) -> ...` | `base.py` |
| `delete_branch_in_git(...) -> ...` | `base.py` |
| `update_commit_value(branch_name: str, commit: str) -> bool` | `base.py:628` |

### Invariants

- Both protocols are derived from existing behavior; no method on the protocol is unimplemented on either concrete class. Verified by an LSP-style structural check in the protocol PR.
- `InfrahubReadOnlyRepository` satisfies `RepositoryProtocol` as well as `ReadOnlyRepositoryProtocol` — its write methods inherit from the integrator/base and exist at runtime even if some raise. (Spec FR-006 only requires that the read-only protocol exposes the read-side capabilities; consumers that want strict read-only typing use that protocol.)
- Re-exported via `infrahub.git.repository` (FR-013).

---

## 2. `RepositoryFileImporter` collaborator

Lives in `backend/infrahub/git/importer/__init__.py` with per-type handlers in sibling files.

### `RepositoryFileImporter` class

```python
class RepositoryFileImporter:
    repository: RepositoryProtocol
    handlers: list[FileImportHandler]

    def __init__(self, repository: RepositoryProtocol) -> None: ...
    def register(self, handler: FileImportHandler) -> None: ...
    async def import_all(self, *, infrahub_branch_name: str, commit: str) -> None: ...
    async def import_one(self, *, handler_name: str, infrahub_branch_name: str, commit: str) -> None: ...
```

### `FileImportHandler` protocol

```python
class FileImportHandler(Protocol):
    name: str
    config_section: str  # key under .infrahub.yml that this handler reads

    async def discover(self, repository: RepositoryProtocol, *, commit: str) -> Sequence[DiscoveredFile]: ...
    async def reconcile(
        self,
        repository: RepositoryProtocol,
        *,
        files: Sequence[DiscoveredFile],
        infrahub_branch_name: str,
        commit: str,
    ) -> None: ...
```

`reconcile` owns the compare/create/update flow that today lives inline in each `import_*` method on the integrator.

### Built-in handlers (Story 4, one per object type)

| Handler | Replaces method on integrator | File |
|---|---|---|
| `SchemaFileHandler` | `import_schema_files` (integrator.py:513) | `importer/schema.py` |
| `GraphqlQueryHandler` | `import_all_graphql_query` (585) | `importer/graphql_query.py` |
| `PythonCheckHandler` | `import_python_check_definitions` (657) | `importer/python_check.py` |
| `GeneratorHandler` | `import_generator_definitions` (728) | `importer/generator.py` |
| `PythonTransformHandler` | `import_python_transforms` (820) | `importer/python_transform.py` |
| `Jinja2TransformHandler` | `import_jinja2_transforms` (241) | `importer/jinja2_transform.py` |
| `ArtifactDefinitionHandler` | `import_artifact_definitions` (346) | `importer/artifact_definition.py` |

### Composition

The integrator's `__init__` (or Pydantic model `__init__`, depending on which lifecycle the SDK-client PR leaves usable) instantiates a `RepositoryFileImporter(repository=self)` and pre-registers the built-in handlers in deterministic order. The eight integrator methods named above become one-line delegates (FR-016):

```python
async def import_schema_files(self, *, infrahub_branch_name: str, commit: str) -> ...:
    return await self.file_importer.import_one(
        handler_name="schema", infrahub_branch_name=infrahub_branch_name, commit=commit,
    )
```

The delegate is removed only in the final Story 4 cleanup PR.

---

## 3. Error-pattern registry

`backend/infrahub/git/errors.py`:

```python
@dataclass(frozen=True, slots=True)
class ErrorContext:
    name: str
    branch_name: str | None = None
    location: str | None = None

@dataclass(frozen=True, slots=True)
class ErrorRule:
    matcher: Callable[[str], bool]
    factory: Callable[[ErrorContext, GitCommandError], Exception]

def any_substring(*needles: str) -> Callable[[str], bool]: ...
def any_substring_ci(*needles: str) -> Callable[[str], bool]: ...  # case-insensitive
def all_substrings(*needles: str) -> Callable[[str], bool]: ...     # AND across needles

# Named module-level builders — one per exception shape. Reused across rules.
def _connection_error(ctx: ErrorContext, _exc: GitCommandError) -> Exception:
    return RepositoryConnectionError(identifier=ctx.name)

def _credentials_error(ctx: ErrorContext, _exc: GitCommandError) -> Exception:
    return RepositoryCredentialsError(identifier=ctx.name)

def _invalid_branch_error(ctx: ErrorContext, _exc: GitCommandError) -> Exception:
    return RepositoryInvalidBranchError(
        identifier=ctx.name, branch_name=ctx.branch_name, location=ctx.location,
    )

def _merge_repository_error(ctx: ErrorContext, exc: GitCommandError) -> Exception:
    return RepositoryError(identifier=ctx.name, message=exc.stderr)

ERROR_RULES: tuple[ErrorRule, ...] = (
    ErrorRule(any_substring("Repository not found",
                            "does not appear to be a git",
                            "Failed to connect to"),         _connection_error),
    ErrorRule(any_substring("error: pathspec"),               _invalid_branch_error),
    # ... one entry per existing if-branch; see contracts/error-registry.md for full list ...
)

def raise_enriched(error: GitCommandError, *, context: ErrorContext) -> NoReturn:
    for rule in ERROR_RULES:
        if rule.matcher(error.stderr):
            raise rule.factory(context, error) from error
    raise RepositoryError(identifier=context.name, message=error.stderr) from error
```

### Invariants

- Rules are evaluated in tuple order; first match wins. Matches the existing top-to-bottom semantics of `_raise_enriched_error_static` (`base.py:1083-1115`).
- The fallthrough generic `RepositoryError` raise stays — it's the loop's else clause.
- The base class's existing static method becomes a thin wrapper around `raise_enriched` (no caller-visible change) until callers migrate; Story 2 lands the registry as additive, the migration happens opportunistically in subsequent PRs that touch the area.

---

## 4. Workflow wrapper / plain-impl split

Per FR-008 and FR-021, every Prefect-decorated method on `InfrahubRepositoryIntegrator` is split into a pair:

```python
class InfrahubRepositoryIntegrator(InfrahubRepositoryBase):
    async def _import_schema_files_impl(
        self, *, infrahub_branch_name: str, commit: str,
    ) -> ImportResult:
        # plain async body — moved verbatim from the current decorated method
        ...

    @task(name="import-schema-files", task_run_name="...", retries=3)
    async def import_schema_files(
        self, *, infrahub_branch_name: str, commit: str,
    ) -> ImportResult:
        return await self._import_schema_files_impl(
            infrahub_branch_name=infrahub_branch_name, commit=commit,
        )
```

### Invariants

- The `_impl` method is private (leading underscore) and is the one unit tests call.
- The decorated wrapper keeps the public name, decorator, and signature — call sites and existing Prefect flows are unchanged (FR-014, FR-013).
- In-process callers, including recursive self-calls, go through the wrapper, not `_impl` (FR-021). This preserves Prefect retry, checkpointing, telemetry, and structured-logging behavior.
- Any deviation (e.g., a hot loop where the wrapper overhead matters) is documented in an ADR under `dev/adr/` (FR-021).

---

## 5. Constructor and SDK-client lifecycle (Story 6)

### Default-branch injection (FR-009)

`InfrahubRepositoryBase` gains an optional constructor parameter:

```python
class InfrahubRepositoryBase(BaseModel):
    default_branch_name: str | None = None  # already present
    # no new Pydantic field; the @property fallback chain stays
```

Tests can now construct with `default_branch_name="custom"` directly. No existing caller is required to change.

### SDK-client initialization (FR-010)

Replace the lazy property:

```python
# before — base.py:183
@property
def sdk(self) -> InfrahubClient:
    if not self.client:
        self.client = get_client()  # mutates a Pydantic field from a read accessor
    return self.client
```

with explicit initialization. Two acceptable shapes:

1. Pydantic `model_validator(mode="after")` that calls `get_client()` if `client` is `None` — runs once at construction, no mutation from a read accessor.
2. A `configure_sdk_client(client: InfrahubClient | None = None)` method called by the existing factory(ies); the factory passes a client in production, tests pass a fake.

Option 1 is the smaller blast radius and is the default. The PR documents the choice.

### Invariants

- After construction, reading `repo.client` twice does not mutate `repo`. (FR-010 acceptance.)
- The existing global `get_client()` lookup is still the source of the default — no behavior change. (FR-014.)
- All existing call sites continue to work without edits. (FR-009.)

---

## 6. Suppression footprint (Story 2 carries the invariant)

Tracked as data, not entities, but recorded here for completeness:

| Source | Today | Direction |
|---|---|---|
| `[[tool.mypy.overrides]] module = "infrahub.git.base"` | `arg-type, attr-defined, index, return-value` | Story 3 (protocols) may narrow `attr-defined`. Story 2 (merge annotation) may narrow `return-value`. |
| `[[tool.mypy.overrides]] module = "infrahub.git.repository"` | `arg-type, assignment, call-overload, return-value` | Story 5 (workflow split) is expected to obsolete `call-overload`. Story 2's commit-value docstring narrows nothing automatically; renames are out of scope. |
| ty rule override for `backend/infrahub/git/**` | (read from `pyproject.toml` at Story 2 PR open time) | Same direction as mypy: narrow as code structure permits. |
| Inline `# type: ignore[call-overload]` × 13 in `integrator.py` | present | Story 5 removes these per-PR as wrappers split. |
| Inline `# type: ignore` elsewhere (~14 across base/repository/tasks) | present | Removed opportunistically. |

FR-018 invariant: the union never grows. FR-019: removed-or-narrowed in the same PR that obsoletes them. No new inline `# type: ignore` introduced.
