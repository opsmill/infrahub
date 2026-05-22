# Contract: Public Import Surface

**Source of truth**: FR-013 of `spec.md`. Every name listed below MUST remain importable from the path shown, with the same name, after every PR in this work.

## `infrahub.git` (package root)

Defined by `backend/infrahub/git/__init__.py`. Current `__all__`:

```python
__all__ = [
    "InfrahubReadOnlyRepository",
    "InfrahubRepository",
    "initialize_repositories_directory",
]
```

After this work: identical. Adding entries (e.g., `ReadOnlyRepositoryProtocol`, `RepositoryProtocol`) is permitted; removing or renaming any of the three above is not.

## `infrahub.git.repository`

The most heavily-imported module. The following symbols MUST remain importable by name:

| Name | Kind | Today's defining line |
|---|---|---|
| `InfrahubRepository` | class | `repository.py:26` |
| `InfrahubReadOnlyRepository` | class | `repository.py:214` |
| `get_initialized_repo` | function (Prefect `@task`) | `repository.py:320` |

After this work, the following symbols are additionally importable from this path (re-exported from `protocols.py`):

| Name | Kind |
|---|---|
| `ReadOnlyRepositoryProtocol` | `typing.Protocol` |
| `RepositoryProtocol` | `typing.Protocol` |

## `infrahub.git.base`

Public symbols imported elsewhere in the backend MUST remain importable. Confirmed by `grep` before any structural PR that touches `base.py`. The protected list currently includes:

- `InfrahubRepositoryBase`
- `RepoFileInformation`, `RepoChangedFiles`, `BranchInGraph`, `BranchInRemote`, `BranchInLocal`
- Any exception classes referenced by name from outside the module

## `infrahub.git.integrator`

- `InfrahubRepositoryIntegrator` — class
- `ArtifactGenerateResult`, `CheckDefinitionInformation`, `TransformPythonInformation` — Pydantic models

## `infrahub.git.tasks`

Existing public surface preserved. Story 5's workflow-decorated wrappers do NOT move out of `infrahub.git.integrator` into this module if doing so would change a public name; the spec FR-008 says the wrapper "lives in the workflow module" only where that doesn't break FR-013. The default for this work: wrappers stay where they are today, only the body is extracted into the underscored `_impl` method.

## `infrahub.git.models`

The 16 Pydantic request/configuration models stay where they are; no rename.

## `infrahub.git.utils`

Unchanged.

## Verification

Each PR runs a static check that diffs the set of names exported from every module in `backend/infrahub/git/` against `develop` at the PR's tip. New names: fine. Missing or renamed names: PR blocks. SC-004 codifies this.

Concretely, the check is a small script (or one-liner) that imports each module and compares `dir(module)` against the baseline, ignoring names beginning with `_`. The baseline is the symbol set on `develop` at the time the work starts and is updated only by an explicit PR.
