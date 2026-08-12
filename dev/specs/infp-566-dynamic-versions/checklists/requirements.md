# Specification Quality Checklist: Dynamic Versioning from Git Tags

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-11
**Re-validated**: 2026-05-12 (against spec baseline commit `2406fae3c`)
**Feature**: [spec.md](../spec.md)

> **Re-validation summary**: The spec has been substantially expanded since the initial 2026-05-11 draft. User stories grew from 5 to 6 (added US6 for release-orchestration tasks). Functional requirements grew from 15 to 22 (added FR-016 through FR-022 covering dead-code deletion, release-task rework, CI workflow migrations, Docker version-resolution path, the `/cut-release` slash command, and maintenance-release safety). A new Open Questions section captures four deferred decisions (OQ-1 through OQ-4) with named owners and deadlines. The validation items below have been re-checked against the current state of the spec; items where the answer has shifted since the initial pass are annotated, and a new Cross-Artifact Consistency section has been added.

## Content Quality

- [x] No undue implementation details (languages, frameworks, APIs)
  - Spec names `hatch-vcs` as an example resolver, BuildKit bind mounts, `importlib.metadata`, `actions/checkout`, `uv version --short`, `tomllib`/`tomli`, towncrier internals, and several other concrete tools. These are problem-domain references, not premature design. FR-013 explicitly leaves the resolver choice open; OQ-1 explicitly leaves the Docker mitigation choice open. The level of concretion has grown since the initial draft but is necessary for build-system unambiguity.
- [x] Focused on user value and business needs at the user-story level
  - Each FR maps back to at least one user story; the mapping is traceable.
- [~] Written for non-technical stakeholders
  - User stories, operational Edge Cases, Success Criteria, and Out of Scope remain stakeholder-readable. The Functional Requirements and Open Questions sections are now squarely engineer-facing (line-number citations, file paths, packaging-tool internals). This is a deliberate trade-off — a build-system spec without that detail isn't actionable. Initial draft was checked; current state is more honestly "partially met for the user-story layer, not for the FR layer."
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No `[NEEDS CLARIFICATION]` markers remain
  - Literal: true. Spiritually: the spec now has a dedicated Open Questions section (OQ-1 through OQ-4) tracking deferred decisions, each with a named owner and a "decision required before" deadline. These are not gaps being ignored — they are gaps explicitly scheduled to be resolved before specific points in the implementation lifecycle.
- [x] Requirements are testable and unambiguous
  - 22 FRs each carry a specific verifiable outcome and (where applicable) a baseline-commit-anchored file/line citation.
- [x] Success criteria are measurable
  - SC-001 through SC-006 are all stated as outcomes that can be measured in the next 1-2 release cycles after the change lands.
- [x] Success criteria are technology-agnostic at the outcome level
  - SC-006 names "Helm chart `appVersion`" and "`docker-compose.yml` image-tag bump" — these are domain artifacts that the release pipeline produces, not implementation choices internal to this feature. Defensible.
- [x] All acceptance scenarios are defined
  - US1-US6 each have a numbered acceptance-scenario list. US6 specifically references the FRs that produce its outcomes (e.g., AC4 → FR-019, AC5 → FR-022).
- [x] Edge cases are identified
  - Edge-case set has been substantially expanded since initial draft. Now covers technical edge cases (shallow clones, malformed tags, fork PRs, multiple pre-release tags) AND operational edge cases (workflow trigger never firing under the old `paths:` filter, editable-install version staleness, sdist-rebuild fallback, `uv version --short` on dynamically-versioned projects).
- [x] Scope is clearly bounded
  - Out of Scope section was expanded to explicitly exclude redesigning the post-release automation flow itself.
- [x] Dependencies and assumptions identified
  - Assumptions section was expanded with: backend `__version__` already migrated, towncrier auto-resolution via `package = "infrahub"`, uv workspace membership of both packages, and the bootstrap-version-line consistency (current `1.9.3`, fallback `1.10.0.dev0`, next planned line `1.10`).

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
  - 22 FRs with specific verifiable outcomes. FR-013 and FR-015 are "assessment" FRs whose acceptance is "the assessment is documented and a decision is recorded"; this is appropriate for items where the spec deliberately defers to implementer/release-engineering judgment.
- [x] User scenarios cover primary flows
  - US1 (release without bump PR), US2 (merge without version conflicts), US3 (build always produces usable version), US4 (untagged dev builds identifiable), US5 (runtime/internal tooling reads correct version), US6 (release-orchestration tasks continue to work).
- [x] Feature meets measurable outcomes defined in Success Criteria
  - Each user story has at least one corresponding SC. US6's new addition (release-task safety) is covered by SC-004 and SC-006.
- [~] No implementation details leak into the user-facing specification
  - User stories and Success Criteria remain free of implementation specifics. The FRs and Open Questions deliberately do contain implementation specifics where needed for unambiguity. Same trade-off as "Written for non-technical stakeholders" above.

## Cross-Artifact Consistency (added at re-validation)

- [x] File path + line number citations are anchored to a recorded baseline commit
  - Frontmatter records baseline `develop @ 2406fae3c` (2026-05-11) and explicitly notes that line citations marked "at spec time" need re-verification against any later baseline.
- [x] Every Open Question has a decision owner and a "decision required before" deadline
  - OQ-1: implementer, before FR-020 implementation begins.
  - OQ-2: implementer, before merge.
  - OQ-3: release engineering, before first dynamic-versioning release is published to PyPI.
  - OQ-4: implementer, before FR-017 implementation begins.
- [x] Cutover ordering constraints are explicit and traced
  - FR-019 MUST land in the same commit (or earlier on the same release-train branch) as FR-001/FR-002. Otherwise there is a window where neither the old trigger nor the new trigger fires on releases.
  - FR-021 MUST land in the same change as FR-001/FR-008. Otherwise the team's `/cut-release` command fails immediately on Step 1.
  - FR-022's `>` comparison tightening lands with FR-017's task rework (same FR-017 implementation scope).
- [x] Each FR that touches code or configuration cites a specific file path
  - FR-001 / FR-002 / FR-008: `pyproject.toml`, `python_testcontainers/pyproject.toml`, `uv.lock`, `python_testcontainers/uv.lock`
  - FR-009 / FR-010 / FR-016 / FR-017 / FR-022: `tasks/utils.py`, `tasks/release.py` with specific functions and line numbers
  - FR-011 / FR-020: `.dockerignore`, `development/Dockerfile`, `.devcontainer/Dockerfile`, `utilities/benchmark/Dockerfile`
  - FR-014: `.github/workflows/` (all checkout steps)
  - FR-018: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/update-compose-file-and-chart.yml` with line numbers
  - FR-019: `.github/workflows/update-compose-file-and-chart.yml`
  - FR-020 (Docker workflows): `publish-preview-dev-docker-image.yml`, `publish-dev-docker-image.yml`, `schedule-publish-docker-image.yml`, `ci-docker-image.yml`, and the docker image build in `release.yml`
  - FR-021: `dev/commands/cut-release.md`
- [x] Maintenance-release / non-main-line release operational shape is captured
  - FR-022 + US6 AC5 + FR-012's maintenance-branch-hygiene clause cover the case of `1.11.x` patch releases shipping after `1.12.x` is current.
- [x] Bootstrap state is consistent with the chosen fallback
  - Most recent tag: `infrahub-v1.9.3`. Both `pyproject.toml` files currently declare `version = "1.9.3"`. Fallback: `1.10.0.dev0`. Next planned release line: `1.10`. Verified at re-validation by direct repo inspection. No tag backfill required.

## Notes

**Updated at re-validation (2026-05-12):**

- The fallback value was changed from the initial draft's `1.10.0a0` to `1.10.0.dev0` (canonical PEP 440 form; lower precedence than any pre-release on the `1.10.0` line, which is the desired property for a fallback). See Key Entities in the spec for the ordering rationale.
- Open Issue #3 (Enterprise pipeline, from the original Jira ticket) remains scoped as an *assessment* obligation via FR-015 — that framing is unchanged.
- Open Issue #4 (Docker build, from the original Jira ticket) has been *promoted* from "assess" to "mandate a specific change." FR-011 names the failure mode (`.dockerignore` excludes `.git*`, build resolver has no git history, silently falls back). FR-020 mandates the change with four enumerated mitigation options. The choice between mitigations is tracked as OQ-1 with a documented recommendation.
- The spec now explicitly handles maintenance releases on older version lines (FR-022, US6 AC5, FR-012 hygiene clause). This was a gap in the initial draft, surfaced during late-stage review; see conversation history for the meta-discussion on why the gap persisted across multiple passes.
- Items requiring spec updates before `/speckit-clarify` or `/speckit-plan`: none identified at this re-validation. Recommendation: run `/speckit-clarify` next as a structured-question pass (the spec is coherent enough for it now, and the maintenance-release miss demonstrated that structured passes catch gaps conversational review can miss). Then `/speckit-plan` follows clarification.
- The Open Questions section is the appropriate vehicle for tracked-but-deferred decisions. Reviewers should not treat OQ-1 through OQ-4 as spec defects; they are explicit, owned, and scheduled.
