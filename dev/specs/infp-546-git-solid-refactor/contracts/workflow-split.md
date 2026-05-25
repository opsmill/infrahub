# Contract: Workflow Wrapper / Plain Impl Split (Story 5, FR-008, FR-021)

For every Prefect `@flow` / `@task`-decorated method on `InfrahubRepositoryIntegrator` (see research.md §"Workflow-decorated methods"), this work produces a pair:

## Shape

```python
class InfrahubRepositoryIntegrator(InfrahubRepositoryBase):
    # PRIVATE plain async impl — unit-testable, no Prefect runtime needed.
    # The signature mirrors the wrapper exactly (same parameter names, same
    # types, same return type); the body is whatever lives inside the wrapper
    # at integrator.py:513 today, moved verbatim.
    async def _import_schema_files_impl(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig,
    ) -> None:
        ...

    # PUBLIC decorated wrapper. The decorator and signature below are exactly
    # what integrator.py:513 ships today; the Story 5 split is body-only, so the
    # decorator arguments (name, task_run_name, cache_policy) and the wrapper's
    # signature MUST stay unchanged (FR-013, FR-014). Implementors: do NOT modify
    # any of them during the split.
    @task(name="import-schema-files", task_run_name="Import schema files", cache_policy=NONE)
    async def import_schema_files(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig,
    ) -> None:
        return await self._import_schema_files_impl(
            branch_name=branch_name, commit=commit, config_file=config_file,
        )
```

## Invariants

- The decorated wrapper keeps the public name, decorator, decorator arguments, and signature. No call site changes. (FR-013, FR-014.)
- The `_impl` method is private (leading underscore). Unit tests call it directly. (FR-008.)
- **In-process callers — including recursive self-calls within the integrator class — go through the decorated wrapper, NOT `_impl`.** This preserves Prefect retry, checkpointing, telemetry, and structured-logging behavior. (FR-021.)
- Any deviation from the in-process-caller rule above (e.g., a hot loop where wrapper overhead is measured) requires an ADR under `dev/adr/`. (FR-021.)
- No new `# type: ignore` is introduced in the split PR. The 13 existing `[call-overload]` ignores in `integrator.py` are removed as the wrappers are split, in the same PR. (FR-018, FR-019.)

## Decorated methods covered

Story 5 ships one PR per decorated method. The full list, with the file:line they live at today (research.md):

| Method | Decorator | File:Line |
|---|---|---|
| `import_objects_from_files` | `@flow` | integrator.py:184 |
| `import_jinja2_transforms` | `@task` | 241 |
| `import_artifact_definitions` | `@task` | 346 |
| `get_repository_config` | `@task` | 446 |
| `import_schema_files` | `@task` | 513 |
| `import_all_graphql_query` | `@task` | 585 |
| `import_python_check_definitions` | `@task` | 657 |
| `import_generator_definitions` | `@task` | 728 |
| `import_python_transforms` | `@task` | 820 |
| `import_objects` | `@task` | 949 |
| `get_check_definition` | `@task` | 969 |
| `get_python_transforms` | `@task` | 1009 |
| `import_all_python_files` | `@flow` | 1221 |
| `jinja2_template_render` | `@task` | 1231 |
| `python_check_execute` | `@task` | 1253 |
| `python_transform_execute` | `@task` | 1317 |
| `get_initialized_repo` | `@task` (repository.py) | 315 |

17 PRs in Story 5, one per method. Each PR adds at least one unit test in `tests/unit/git/` that exercises the `_impl` method without initializing the workflow engine (Story 5 acceptance scenario 2).

## Workflow-decorated wrapper location

The spec FR-008 says "the workflow-decorated entry point lives in the workflow module and delegates to the implementation". The default interpretation for this work: the wrapper stays on the integrator class (keeping the public path `infrahub.git.integrator.InfrahubRepositoryIntegrator.import_schema_files`) because moving it would change the import path and break FR-013. The "workflow module" framing applies to free-function workflow entry points that live in `infrahub.git.tasks` already; their delegation surface is unchanged here.

If a per-method PR identifies that the wrapper genuinely belongs in `tasks.py` and the move can be done without changing the integrator's public API, the PR documents the move and updates dashboards/alerts that grep on logger names (FR-014's observability call-out).

## Verification

- Per-PR unit test invoking `_impl` directly succeeds without `prefect` setup.
- Per-PR end-to-end test (existing or new) invoking the public wrapper still passes against the Prefect runtime.
- After all 17 PRs land, `grep -r "type: ignore\[call-overload\]" backend/infrahub/git/` returns zero matches.
