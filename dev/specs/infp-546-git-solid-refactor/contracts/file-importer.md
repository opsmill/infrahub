# Contract: RepositoryFileImporter and Handler Registration (Story 4, FR-007)

**Path**: `backend/infrahub/git/importer/__init__.py` (collaborator) and `backend/infrahub/git/importer/<type>.py` (one file per built-in handler).

## Collaborator

The importer's `import_one` / `import_all` accept the same argument set as the
integrator's per-type `import_*` methods today (`branch_name`, `commit`,
`config_file: InfrahubRepositoryConfig`). This keeps the integrator delegate
body to exactly one expression per FR-016 — no argument transformation is
needed at the delegate site.

```python
class RepositoryFileImporter:
    def __init__(self, repository: RepositoryProtocol) -> None:
        self.repository = repository
        self._handlers: dict[str, FileImportHandler] = {}

    def register(self, handler: FileImportHandler) -> None:
        if handler.name in self._handlers:
            raise ValueError(f"handler {handler.name!r} already registered")
        self._handlers[handler.name] = handler

    async def import_one(
        self,
        *,
        handler_name: str,
        branch_name: str,
        commit: str,
        config_file: InfrahubRepositoryConfig,
    ) -> None:
        handler = self._handlers[handler_name]
        files = await handler.discover(
            self.repository, commit=commit, config_file=config_file,
        )
        await handler.reconcile(
            self.repository,
            files=files,
            branch_name=branch_name,
            commit=commit,
            config_file=config_file,
        )

    async def import_all(
        self,
        *,
        branch_name: str,
        commit: str,
        config_file: InfrahubRepositoryConfig,
    ) -> None:
        # Deterministic iteration order from the registration order.
        for handler in self._handlers.values():
            files = await handler.discover(
                self.repository, commit=commit, config_file=config_file,
            )
            await handler.reconcile(
                self.repository,
                files=files,
                branch_name=branch_name,
                commit=commit,
                config_file=config_file,
            )
```

## Handler protocol

```python
class FileImportHandler(Protocol):
    name: str             # unique handler key, e.g. "schema"
    config_section: str   # key under .infrahub.yml the handler reads

    async def discover(
        self,
        repository: RepositoryProtocol,
        *,
        commit: str,
        config_file: InfrahubRepositoryConfig,
    ) -> Sequence[DiscoveredFile]: ...

    async def reconcile(
        self,
        repository: RepositoryProtocol,
        *,
        files: Sequence[DiscoveredFile],
        branch_name: str,
        commit: str,
        config_file: InfrahubRepositoryConfig,
    ) -> None: ...
```

`DiscoveredFile` is a `frozen=True, slots=True` dataclass with at least `path: Path, contents_hash: str, raw: bytes | None`. Exact fields are finalized in Story 4 PR #1.

**Naming note.** Today's `import_objects_from_files` flow (`@flow` at integrator.py:184) uses `infrahub_branch_name` as its parameter name, while the per-type `@task` methods like `import_schema_files` (integrator.py:513) use `branch_name`. The importer follows the per-type convention (`branch_name`) because that is the layer it replaces. The flow-level wrapper continues to call `infrahub_branch_name` at its public surface (FR-013); internally it passes the value through to the importer as `branch_name`.

## Built-in handler registration

The integrator's constructor (`InfrahubRepositoryIntegrator.__init__` or its Pydantic `model_post_init`) pre-registers the built-in handlers in this order:

```python
self.file_importer = RepositoryFileImporter(repository=self)
self.file_importer.register(SchemaFileHandler())
self.file_importer.register(GraphqlQueryHandler())
self.file_importer.register(PythonCheckHandler())
self.file_importer.register(GeneratorHandler())
self.file_importer.register(PythonTransformHandler())
self.file_importer.register(Jinja2TransformHandler())
self.file_importer.register(ArtifactDefinitionHandler())
```

Order matches today's invocation order in `import_objects_from_files` so behavior is preserved (FR-014).

## Integrator delegate shape (FR-016)

Each of the eight integrator `import_*` methods becomes a one-expression delegate that mirrors the integrator method's exact public signature (FR-013):

```python
# Signature taken verbatim from integrator.py:513; do NOT change it.
async def import_schema_files(
    self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig,
) -> None:
    return await self.file_importer.import_one(
        handler_name="schema",
        branch_name=branch_name, commit=commit, config_file=config_file,
    )
```

Exactly one expression in the body — a call. No conditional, no loop, no argument transformation, no return-value transformation (FR-016).

The Prefect `@task` decorator stays on the integrator method (FR-013 keeps the public name and decorator stable). The wrapper-vs-impl split from Story 5 lands separately; Story 4 only swaps the *body*.

## Adding a new object type (open/closed test, FR-007 acceptance)

A new object type `policy`:

1. Add `backend/infrahub/git/importer/policy.py` with `class PolicyHandler:` implementing the protocol.
2. Add `self.file_importer.register(PolicyHandler())` to the integrator's constructor in the same PR.
3. No edit to any existing handler, no edit to `import_objects_from_files`, no edit to the existing `import_*` methods.

If a new method on `RepositoryProtocol` is genuinely needed (e.g., the policy handler needs an accessor the protocol doesn't expose), the same PR adds it to `protocols.py` — but in practice the read-side surface should already cover it.

## Verification

- Story 4 PR #1 (the empty-importer PR): the importer collaborator exists, is wired into the constructor, has at least one round-trip test in `tests/unit/git/test_importer.py` that registers a no-op handler and calls `import_all`.
- Each subsequent Story 4 PR (one per object type): the corresponding integrator method is now a delegate; the test that previously exercised the inline body is moved or updated to exercise the handler directly via the collaborator; the integration test for `import_objects_from_files` still passes end-to-end against the Gogs fixture.
- Final Story 4 PR: the delegate methods on the integrator are removed only after `grep` confirms no in-tree caller still uses them. (FR-016 cleanup.)
