# Contract: RepositoryFileImporter and Handler Registration (Story 4, FR-007)

**Path**: `backend/infrahub/git/importer/__init__.py` (collaborator) and `backend/infrahub/git/importer/<type>.py` (one file per built-in handler).

## Collaborator

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
        self, *, handler_name: str, infrahub_branch_name: str, commit: str,
    ) -> None:
        handler = self._handlers[handler_name]
        files = await handler.discover(self.repository, commit=commit)
        await handler.reconcile(
            self.repository,
            files=files,
            infrahub_branch_name=infrahub_branch_name,
            commit=commit,
        )

    async def import_all(self, *, infrahub_branch_name: str, commit: str) -> None:
        # Deterministic iteration order from the registration order.
        for handler in self._handlers.values():
            files = await handler.discover(self.repository, commit=commit)
            await handler.reconcile(
                self.repository,
                files=files,
                infrahub_branch_name=infrahub_branch_name,
                commit=commit,
            )
```

## Handler protocol

```python
class FileImportHandler(Protocol):
    name: str             # unique handler key, e.g. "schema"
    config_section: str   # key under .infrahub.yml the handler reads

    async def discover(
        self, repository: RepositoryProtocol, *, commit: str,
    ) -> Sequence[DiscoveredFile]: ...

    async def reconcile(
        self,
        repository: RepositoryProtocol,
        *,
        files: Sequence[DiscoveredFile],
        infrahub_branch_name: str,
        commit: str,
    ) -> None: ...
```

`DiscoveredFile` is a `frozen=True, slots=True` dataclass with at least `path: Path, contents_hash: str, raw: bytes | None`. Exact fields are finalized in Story 4 PR #1.

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

Each of the eight integrator `import_*` methods becomes:

```python
async def import_schema_files(
    self, *, infrahub_branch_name: str, commit: str,
) -> ...:
    return await self.file_importer.import_one(
        handler_name="schema",
        infrahub_branch_name=infrahub_branch_name,
        commit=commit,
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
