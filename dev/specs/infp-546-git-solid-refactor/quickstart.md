# Quickstart: Working in the Refactored `infrahub.git` Module

This is a forward-looking quickstart. It describes how a developer interacts with the module **after** the refactor lands. Pieces marked *(after Story N)* gate on that story's PRs being merged.

## Prerequisites

```bash
uv sync --all-groups
uv run invoke backend.test-unit -- backend/tests/unit/git
uv run invoke backend.test-integration -- backend/tests/integration/git
```

The integration suite uses a Gogs container via Testcontainers (`backend/tests/integration/git/conftest.py`). Docker must be running.

## Add a new repository-defined object type *(after Story 4)*

Say you're adding `policy` support — repository-defined policy files that Infrahub ingests.

1. Create `backend/infrahub/git/importer/policy.py`:

   ```python
   from pathlib import Path
   from collections.abc import Sequence
   from infrahub.git.importer import DiscoveredFile, FileImportHandler
   from infrahub.git.protocols import RepositoryProtocol

   class PolicyHandler:
       name = "policy"
       config_section = "policies"

       async def discover(
           self, repository: RepositoryProtocol, *, commit: str,
       ) -> Sequence[DiscoveredFile]:
           config = await repository.get_repository_config(
               branch_name=repository.default_branch, commit=commit,
           )
           return [
               DiscoveredFile(path=Path(p), contents_hash="...", raw=None)
               for p in (config.policies if config else [])
           ]

       async def reconcile(
           self,
           repository: RepositoryProtocol,
           *,
           files: Sequence[DiscoveredFile],
           infrahub_branch_name: str,
           commit: str,
       ) -> None:
           # compare against the graph, create/update/delete as needed
           ...
   ```

2. Register it in the integrator's constructor (`backend/infrahub/git/integrator.py`, right after the existing `self.file_importer.register(...)` calls):

   ```python
   self.file_importer.register(PolicyHandler())
   ```

3. Add a unit test in `backend/tests/unit/git/test_policy_handler.py` that registers `PolicyHandler` against a fake `RepositoryProtocol` and asserts the reconcile call shape.

You did NOT edit `import_objects_from_files`, you did NOT add a new `import_*` method to the integrator, and you did NOT touch any existing handler. The change is reviewable in one sitting.

## Add a new typed exception for a git error pattern *(after Story 2)*

Say you want to recognize `"too many redirects"` and raise `RepositoryConnectionError`.

1. Open `backend/infrahub/git/errors.py`.
2. Add one entry to `ERROR_RULES` — order matters; place it before any rule whose substring it might subsume. The `_connection_error` builder already exists, so this is one line:

   ```python
   ErrorRule(matcher=any_substring("too many redirects"), factory=_connection_error),
   ```

   If your new pattern needs a *different* exception class, add one named builder above the `ERROR_RULES` definition (alongside `_connection_error`, `_credentials_error`, etc.) and reference it from the new rule. `raise_enriched` still does not change.

3. Add a unit test in `backend/tests/unit/git/test_errors.py`:

   ```python
   def test_too_many_redirects_is_connection_error() -> None:
       err = make_git_command_error(stderr="fatal: too many redirects to ...")
       with pytest.raises(RepositoryConnectionError) as exc:
           raise_enriched(err, context=ErrorContext(name="repo"))
       assert str(exc.value)  # message preserved
   ```

That's the entire change. The `raise_enriched` function body is not edited.

## Write a consumer that only needs read access *(after Story 3)*

Use `ReadOnlyRepositoryProtocol` so your function can be unit-tested with a small fake.

```python
from infrahub.git.repository import ReadOnlyRepositoryProtocol

async def render_template(
    repository: ReadOnlyRepositoryProtocol,
    *,
    template_path: str,
    commit: str,
) -> str:
    contents = await repository.get_file_content(commit=commit, file_path=template_path)
    # ...render...
    return rendered
```

In tests:

```python
class FakeRepo:
    name = "fake"
    id = "fake-id"
    default_branch = "main"
    async def get_file_content(self, commit: str, file_path: str) -> str:
        return "{{ greeting }}"
    # ...other read-side methods stubbed as needed

async def test_render_template() -> None:
    repo: ReadOnlyRepositoryProtocol = FakeRepo()  # mypy-checked structurally
    result = await render_template(repo, template_path="t.j2", commit="abc")
    assert "..." in result
```

No mocks, no monkeypatching, no Pydantic-model construction with 15 fields.

## Unit-test business logic without the workflow engine *(after Story 5)*

The integrator's decorated methods now wrap private `_impl` methods. Tests call `_impl` directly:

```python
import pytest
from infrahub.git.integrator import InfrahubRepositoryIntegrator

@pytest.mark.asyncio
async def test_import_schema_files_impl(tmp_path, fake_sdk_client) -> None:
    integrator = InfrahubRepositoryIntegrator(
        name="repo", id="r1", default_branch_name="main",
        client=fake_sdk_client,                     # injected, no global patch
        location=str(tmp_path),                     # ...etc
    )
    result = await integrator._import_schema_files_impl(
        infrahub_branch_name="main", commit="abc123",
    )
    assert result == ...
```

No `prefect` import, no flow-runner setup, no `infrahub.workflow` patching.

## Run the real-remote integration suite *(after Story 1)*

```bash
uv run invoke backend.test-integration -- backend/tests/integration/git/
```

The expanded suite covers the six scenario families from FR-001:

1. Authentication and access — `test_auth_and_access.py`
2. Push failures — `test_push_failures.py`
3. Merge scenarios — `test_merge_scenarios.py`
4. Read-only repository — `test_readonly_repository_real.py`
5. Repository setup — `test_repository_setup.py`
6. Sync with branch-state mismatches — `test_sync_mismatches.py`

Each file is one scenario family; failing one does not block the others. The suite is gated in CI for merges to `develop`.

## Inject a non-default branch name in a test *(after Story 6)*

```python
repo = InfrahubRepository(
    name="repo", id="r1",
    default_branch_name="trunk",   # injected, no patching of registry.default_branch
    # ... other required fields
)
assert repo.default_branch == "trunk"
```

The fallback to `registry.default_branch` still works when `default_branch_name` is omitted — no existing caller has to change.
