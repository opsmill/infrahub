# Contract: Generator `watch:` field in `.infrahub.yml`

Adds a `watch:` field to a generator definition entry in `.infrahub.yml`, reusing the existing `InfrahubWatchConfig`. This is the generator analogue of the transform `watch:` shipped by INFP-409. Because the backend closure aggregator already unions `watch.files` and appends the manifest, adding the SDK field makes generator `watch:` functional end-to-end with no further backend wiring (beyond the FR-002 union widening that lets the aggregator accept the generator config at all).

## Schema

```yaml
# .infrahub.yml
generator_definitions:
  - name: my_generator
    file_path: "generators/my_generator.py"
    class_name: "MyGenerator"
    query: "my_query"
    targets: "my_group"
    parameters:
      name: "name__value"
    watch:                          # NEW, optional
      files:
        - "shared_helpers/"         # directory: matches every tracked file beneath it, recursively
        - "common/constants.py"     # single file outside the generator's package directory
```

## SDK model

`python_sdk/infrahub_sdk/schema/repository.py`:

```python
class InfrahubGeneratorDefinitionConfig(InfrahubRepositoryConfigElement):
    model_config = ConfigDict(extra="forbid")
    # ... existing fields ...
    watch: InfrahubWatchConfig | None = Field(
        default=None,
        description="Extra files and directories this generator depends on, in addition to the ones Infrahub detects automatically.",
    )
```

Reuses the existing model (no new type):

```python
class InfrahubWatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    files: list[str] = Field(default_factory=list, description="...")
```

## Validation rules (FR-015)

| Input | Result |
|---|---|
| `watch: { files: ["a", "dir/"] }` | accepted |
| `watch:` omitted | accepted (`None`; auto-detection only) |
| `watch: { files: [] }` | accepted (empty list; no extra dependencies, completeness unaffected) |
| `watch: ["a", "b"]` (list form) | **rejected** — Pydantic type error (object expected) |
| `watch: { fles: [...] }` (typo / unknown key) | **rejected** — `extra="forbid"` |
| `watch: { files: "a" }` (string not list) | **rejected** — Pydantic type error |

## Closure behavior (FR-016, FR-017) — backend, reused

At import time the aggregator runs `PythonClosure.build()` (package-directory floor), then `append_manifest_path`, then `union_watch_files(transform_config=<generator config>, ...)`:

- Directory entries in `watch.files` are expanded recursively to git-tracked files beneath them (`git ls-files`); `.pyc`, `__pycache__`, and symlinks are skipped.
- A non-empty `watch.files` forces `dependencies_complete = True` — the user has taken responsibility for declaring what auto-detection cannot see.
- A `watch.files` entry matching no tracked file is logged as a **warning** and does not extend the closure, but does not abort the import of that generator or the others (FR-016), and still counts as a declaration for completeness.

## End-to-end effect (FR-014)

Once the field exists and the generator config is accepted by the union (FR-002):

1. A generator declaring `watch.files: ["shared_helpers/"]` re-runs when any file under `shared_helpers/` changes (SC-009).
2. The same generator does **not** re-run for edits outside both the declared `watch.files` and the auto-detected package floor (SC-009).
3. A `watch:` declared in any non-object form is rejected at parse time (SC-009).

## Trust model (Known Limitation, carried from INFP-409)

`watch:` is trusted, not verified. If the declared `files` do not actually cover a runtime import, the generator can still under-run. The system cannot know what dynamic imports resolve to; the mitigation is documentation and the no-match warning log, not enforcement.

## Documentation (FR-012)

Add a generator `watch:` entry to the repository-config schema reference, mirroring the transform `watch:` reference shipped by INFP-409, and extend the dependency-closure / why-trail documentation to mention generators.
