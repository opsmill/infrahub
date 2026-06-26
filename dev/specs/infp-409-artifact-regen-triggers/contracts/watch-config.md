# Contract: `watch:` field in `.infrahub.yml`

User-facing schema added to the repository config (the SDK-owned Pydantic model in `python_sdk/infrahub_sdk/schema/repository.py`). Available on both `python_transforms` and `jinja2_transforms` entries.

## Shape

```yaml
# .infrahub.yml

python_transforms:
  - name: DeviceNameAttribute
    class_name: DeviceNameAttribute
    file_path: transforms/device_name_attribute.py
    watch:
      files:
        - utils/
        - shared/helpers.py

jinja2_transforms:
  - name: DeviceConfig
    query: device_config_query
    template_path: templates/device_config.j2
    watch:
      files:
        - templates/partials/
```

## Field reference

### `watch`

- Type: object (strict — see "Forbidden forms" below).
- Optional. Absent means "auto-detect only".
- Future keys (`strict:`, `exclude:`, etc.) will live under `watch:`. Today only `files:` is defined.

### `watch.files`

- Type: `list[str]`.
- Optional within `watch:`. Defaults to `[]`. (An empty `watch:` block — `watch: {}` — is a no-op.)
- Each entry is either a file path or a directory path, both relative to the repository root.
- Directory entries match **recursively** — every tracked file under the directory enters the closure.
- Entries may be written with or without a trailing slash; the backend integrator canonicalizes them.
- Symlinks under directory entries are silently skipped (see Decision 8 in research.md).
- `.gitignore`d files, `.pyc`, and `__pycache__/` are never included regardless of `watch.files` (FR-006 + Decision 6 in research.md).

## Forbidden forms

The schema is strict (Pydantic `model_config = ConfigDict(extra="forbid")`). The following are rejected at parse time with a clear error:

| Form | Why rejected |
|---|---|
| `watch: [utils/, shared/helpers.py]` (list at the field) | FR-011: object-only, no list/object union. |
| `watch: { fles: [...] }` (typo on key) | `extra="forbid"` catches unknown keys. |
| `watch: utils/` (string) | Not an object. |
| `watch: {}` with no `files:` AND a sibling `strict: false` | `strict` is not yet defined; rejected as unknown key. |

## Semantics — closure union

At git-import time, the backend integrator computes the final closure as:

```text
final_closure = (auto_detected_closure ∪ canonicalize(watch.files entries)) ∪ {.infrahub.yml}
```

Where:

- `auto_detected_closure` is the output of the per-language closure builder (Jinja2 AST walk via `jinja2.meta.find_referenced_templates`, or the Python package-directory floor).
- `watch.files` directory entries are expanded recursively to the set of files they contain at the worktree checkout, then each file is canonicalized.
- The manifest path (`.infrahub.yml`) is appended unconditionally.

The result is stored sorted on `CoreTransformation.dependencies`.

## Completeness rule

```text
dependencies_complete = (auto_detection_had_no_unresolved_refs) OR (watch.files is declared and non-empty)
```

- Auto-detection found no unresolved references → `True`.
- Auto-detection found one or more unresolved references AND `watch.files` is absent or empty → `False`.
- Auto-detection found unresolved references AND `watch.files` is non-empty → `True` (trusting the user — FR-014; Known Limitation: incorrect declaration → under-regeneration).

## Backwards compatibility

The field is fully optional. Repositories that do not declare `watch:` continue to work — Python uses the package-directory floor, Jinja2 uses the AST walk. Existing transforms without `watch:` are fine.

For pre-feature transforms with `dependencies = null`, the pipeline falls back to today's behavior until the next natural re-import (Decision 11 in research.md). Adding `watch:` to a transform takes effect on the *next* import after the change is committed.

## Validation timing

- **At parse time (SDK):** The Pydantic model rejects malformed shapes (object form, no unknown keys, `files` is a `list[str]`).
- **At import time (backend):** Each `files` entry is canonicalized; directory entries are walked. Failures (unreadable path, glob errors) trigger the closure-builder failure path (Decision 9 in research.md) — the transform's `dependencies_complete` is set to `False`, the failure is logged with the transform's identity, and the import continues for other transforms.

## Documentation deliverable (alongside code)

The reference page under the `.infrahub.yml` documentation must include:

- The strict object form with the `files:` key.
- A note that directory entries match recursively.
- A statement that future keys will live under `watch:`.
- One worked example for `python_transforms` and one for `jinja2_transforms`.

See spec.md "Documentation Deliverables" for the full doc-deliverable list.
