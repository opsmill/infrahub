# Phase 0 Research

This document resolves the technical unknowns that informed the spec and the plan. The source investigation (`dev/specs/infp-409-artifact-regeneration-investigation.md`) is the authoritative deep-dive; this file records the choices and the alternatives weighed.

There are no remaining `NEEDS CLARIFICATION` markers — the investigation pre-resolved them.

## Decision 1 — Walk file dependencies at git-import time, not pipeline time

**Decision**: Build each transform's dependency closure once at import time (when the repo is integrated for a commit) and store it on the transform node. At pipeline time, the regeneration question for a transform is a Python set intersection between the stored closure and the per-repo file diff.

**Rationale**:

- Pipeline-time walking would re-parse every transform on every proposed change, multiplying work by `definitions × commits_seen_in_PC`. Import-time walking pays the cost once per commit on the repo and amortizes it across every proposed change that compares against that commit.
- The closure is a property of the transform's *source content*, which only changes when the repo is re-integrated. Storing it on the node aligns lifecycle with content.
- The intersection is O(|closure| + |diff|) per definition with cheap operations; pipeline latency stays flat as repositories grow.

**Alternatives considered**:

- *Pipeline-time walk.* Rejected on cost and on coupling: pipeline code would need to re-open the worktree and re-parse templates, growing the pipeline's responsibility surface.
- *Hash-only compare (Phase 3 in the investigation).* Closes additional gaps (cross-branch edit-then-revert, per-entry manifest granularity) but does not by itself answer "which definition is impacted by which file?" — would still need a closure to answer that. Deferred per spec Out of Scope.

## Decision 2 — Two attributes on `CoreTransformation` generic, not on each specialization

**Decision**: Add `dependencies: list[str]` and `dependencies_complete: bool` to `CoreTransformation` (the generic). Both specializations (`CoreTransformJinja2`, `CoreTransformPython`) inherit.

**Rationale**:

- The pipeline check is kind-agnostic by construction — it does not care whether the transform is Jinja2 or Python.
- Future detection mechanisms (e.g. `watch.strict:` would let Python produce `dependencies_complete = False`) attach to the generic without schema migration.
- Per FR-026, this lives at the generic level.

**Alternatives considered**:

- *Per-specialization attributes.* Rejected: would force a kind switch in the pipeline check and would require schema migration when Python ever gains a completeness signal.

## Decision 3 — `watch:` is a strict object, not a list/object union

**Decision**: `watch:` on `python_transforms` and `jinja2_transforms` is a Pydantic `BaseModel` with `model_config = ConfigDict(extra="forbid")` and a single required field `files: list[str]`. List form is rejected at schema-load time.

**Rationale**:

- The SDK ships type definitions consumed by non-Python clients (typed languages); a polymorphic shape would not round-trip cleanly.
- An object lets future keys (`strict:`, `exclude:`, etc.) land additively without breaking parsers.
- Strict-mode (extra-forbid) catches typos at import time with a clear error.

**Alternatives considered**:

- *List shorthand (`watch: [a, b]`) unioned with object form.* Rejected per FR-011 — strict typing wins.
- *Top-level `watch_files:` field.* Rejected because it precludes namespaced future keys.

## Decision 4 — Path canonicalization is a single shared helper, called from import path and pipeline path

**Decision**: Define one canonicalizer in `backend/infrahub/git/closure_builder/canonicalizer.py` that turns any input path (user `watch.files` entry, auto-detected closure path, git diff file path) into the canonical form: repo-relative, POSIX separators, no leading `./`, no trailing slash, no symlink resolution. Call it from both the closure builder (storing into `dependencies`) and the pipeline-time predicate (reading from `files_changed`).

**Rationale**:

- The intersection check is silently incorrect if the two sides normalize differently. One shared callee removes that hazard.
- POSIX separators are the form git uses internally; aligning with that avoids platform drift.
- No symlink resolution preserves the "user declares the real target via `watch:`" contract (Decision 6 below).

**Alternatives considered**:

- *Normalize at write time only and trust diff data.* Rejected: `files_changed` paths come from the git diff and may carry trailing slashes for directories or leading `./` depending on how the diff is computed; symmetric normalization is the only safe option.

## Decision 5 — Jinja2 closure builder uses `jinja2.meta.find_referenced_templates`, continues past unresolved references

**Decision**: For Jinja2 transforms, parse with `jinja2.Environment.parse()` (using `FileSystemLoader` rooted at the commit worktree, identical to the runtime renderer) and walk references via `meta.find_referenced_templates`. When the function yields `None` (non-literal include name), record the unresolved site and keep walking. Mark `dependencies_complete = False` if any `None` was seen and `watch.files` was not declared.

**Rationale**:

- Jinja2's stdlib `meta` module is the supported way to enumerate template references and is what the runtime resolver implicitly uses; reusing it keeps the closure aligned with what the engine actually loads.
- Continuing past `None` (per FR-023a) gives users a lower-bound dependency list and a complete picture of unresolved sites in one import pass.
- Using the same `FileSystemLoader` root as the runtime (commit worktree directory) means paths are repo-relative by construction and match the canonical form.

**Alternatives considered**:

- *Stop at first `None`.* Rejected: users with multiple dynamic includes would have to iterate import-by-import to find them all.
- *AST traversal bypassing `meta`.* Rejected: the stdlib helper is correct, well-tested, and free.

## Decision 6 — Python closure is a "package directory floor", no AST import analysis

**Decision**: For Python transforms, the closure is every `.py` file (and other tracked files) under the package directory of `file_path`, excluding `.pyc`, `__pycache__/`, and gitignored entries. Plus any `watch.files` entries. `dependencies_complete` is always `True` for Python under this design.

**Rationale** (paraphrased from the investigation):

- AST-precise import analysis was considered and rejected: `importlib`, `__import__`, runtime imports inside functions, and `exec` on file content are invisible to it. Missing one silently violates the correctness invariant.
- The package-directory floor catches the common pattern (transform + sibling helpers) with zero user effort.
- Cross-package dependencies are an explicit user opt-in via `watch.files`, which is the same escape hatch Jinja2 uses for dynamic includes.

**Alternatives considered**:

- *`importlab` / AST walker.* Rejected as above.
- *Always require `watch.files` for Python.* Rejected: hostile to the common case (single-file or single-package transforms).

## Decision 7 — Manifest path (`.infrahub.yml`) is part of every transform's closure

**Decision**: The closure builder appends the canonical path to `.infrahub.yml` to every transform's `dependencies` list in that repository.

**Rationale**:

- Per FR-021, any edit to the manifest conservatively regenerates all transforms in that repo. Over-regeneration here is acknowledged and acceptable until per-entry granularity ships (deferred).
- Putting the manifest path *in the closure* rather than special-casing it at the predicate keeps the intersection check uniform — the predicate does not need to know about `.infrahub.yml` at all.

**Alternatives considered**:

- *Special-case the manifest at the predicate.* Rejected as scattered logic; the closure is the right level.
- *Per-entry manifest fingerprint.* Deferred (Phase 3 territory).

## Decision 8 — Symlinks are silently skipped

**Decision**: When the closure builder encounters a symlink (Python heuristic floor walk or `watch.files` entry), it is not followed and not added to the closure. Users with symlinks declare the real target via `watch.files`.

**Rationale**:

- Following symlinks could escape the repo root and add untracked files (or worse, files outside the worktree) to the closure.
- The user is the closest authority on what the symlink points to and whether it should be tracked.

**Alternatives considered**:

- *Follow symlinks within the repo.* Rejected: hard to define "within the repo" post-resolve, and silent over-inclusion is the wrong default.
- *Error on symlinks.* Rejected: would block import for repos that have unrelated symlinks elsewhere in the package directory.

## Decision 9 — Closure-builder failures are logged and isolated; the import continues

**Decision**: A closure-builder failure for one transform (malformed Jinja2 template, unreadable `watch.files` path, IO error) is caught at that transform's boundary. The error is logged with the affected transform's identity, `dependencies_complete = False` is recorded on that transform, and the import continues for the remaining transforms in the repository.

**Rationale**:

- Per FR-023 and User Story 4, one bad transform must not block updates to unrelated transforms.
- `dependencies_complete = False` ensures the affected transform falls back to today's regenerate-on-anything behavior — the safety invariant holds.

**Alternatives considered**:

- *Fail the whole import on first closure-builder error.* Rejected as a regression in operator UX.
- *Silently skip the transform without logging.* Rejected: hides the failure.

## Decision 10 — Per-repo file diff decoupled from `sync_with_git`

**Decision**: Compute the per-repo file diff for every linked repository, every branch pair, regardless of the source branch's `sync_with_git` attribute. For `CoreRepository`, diff between the source and destination branches' tracked Git branch tips; for `CoreReadOnlyRepository`, diff between the source and destination branches' pinned commits.

**Rationale**:

- Today's gate (`source_branch_sync_with_git AND has_file_modifications`) silently excludes read-only repos.
- The intersection check naturally handles an empty diff: zero files → zero matches → no regeneration on file-change grounds. No special case needed.
- For `CoreRepository` with `sync_with_git = False`, the tracked commits don't move, so the diff is naturally empty. The flag is now redundant in this code path.

**Alternatives considered**:

- *Keep the flag for `CoreRepository` and only special-case read-only.* Rejected: scattered logic, easy to drift.

## Decision 11 — Backward compatibility via `dependencies is null` sentinel

**Decision**: Use `null` (not `[]`) on `dependencies` to mean "no information yet — fall back to legacy behavior for this transform". The pipeline predicate treats `null` as "regenerate on any file change in this repo" (today's behavior, per-transform).

**Rationale**:

- `[]` is a legitimate value (a transform that genuinely depends on nothing in the repo — unusual but valid).
- Per-transform self-heal: as each transform is re-imported under the new code, its `dependencies` is populated and it switches to the new gate on the next proposed change.
- Operators do not run a backfill (SC-005).

**Alternatives considered**:

- *Mandatory backfill step.* Rejected: blocks adoption.
- *Treat absent attribute as legacy via schema default.* Same idea, but using a nullable column is the clearest signal.

## Decision 12 — Diagnostic logging via the existing Prefect logger surface, no new attribute

**Decision**: All regeneration-decision logs and import-time closure-builder logs use the same Prefect logger already used by the integrator for schema/query/transform imports and by the pipeline for task progress. No new attribute on the transform node for "why" — the log is the surface.

**Rationale**:

- The repository's task log in Infrahub is the existing surface users already consult.
- Per FR-022, FR-023, FR-023a — the requirement is logs, not stored explanations.
- Avoids a node-attribute bloom for diagnostic strings that would become stale.

**Alternatives considered**:

- *New attribute `last_regeneration_reason` on the definition or transform.* Rejected as scope-creep and storage of mutable diagnostic state.

## Decision 13 — Stage 1 / Stage 2 sequencing

**Decision**: Stage 1 (selection-gate predicates against `diff_summary`) ships before Stage 2 (closure attributes + SDK `watch:` schema) within the same feature delivery, or in the same release. They can be merged in two PRs or one. The spec's "in the interval between the stages" paragraph defines the interim behavior if Stage 1 ships first.

**Rationale**:

- Stage 1 has no schema additions, no SDK coordination, and delivers a meaningful reduction in over-regeneration on its own (per Source Investigation).
- Stage 2 requires schema additions and an SDK release, so it has external dependencies.
- Sequencing protects the correctness invariant either way: Stage 1's residual `has_file_modifications` fallback for transform-file edits matches today's behavior, so no new failure mode is introduced.

**Alternatives considered**:

- *Single-PR landing.* Acceptable too; planning leaves the option open.
- *Stage 2 first.* Rejected — Stage 2 depends on the predicate plumbing Stage 1 sets up (gather query, `ProposedChangeArtifactDefinition` shape), and Stage 1 is the lower-risk landing.

## Decision 14 — `watch.strict:`, per-entry manifest hashing, cross-branch fingerprint compare — deferred

**Decision**: All three are explicitly out of scope for this feature, captured in the spec's Out of Scope and Known Limitations sections.

**Rationale**:

- `watch.strict:` would let Python users disable the package-directory floor in exchange for explicit declarations only. Useful, but not on the critical path for the ticket's motivation.
- Per-entry manifest hashing closes the "edit `.infrahub.yml` for one transform → all transforms regenerate" gap. Over-regeneration only; safe to defer.
- Cross-branch fingerprint compare (Phase 3 in the investigation) closes the edit-then-revert-across-branches gap. Over-regeneration only; safe to defer.

The `watch:` schema is shaped as an object so all three can land later without migration.

## Open items at end of Phase 0

None. The spec is fully clarified; the design is fully chosen. Phase 1 proceeds to data-model + contracts + quickstart.
