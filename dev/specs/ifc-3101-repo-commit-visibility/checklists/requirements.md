# Specification Quality Checklist: Git Repository Commit Visibility

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-03
**Feature**: [spec.md](../spec.md)

## Content Quality

- [ ] No implementation details (languages, frameworks, APIs) — **qualified, deliberately.** FR-004 and SC-005 bound the database query count, and the Governance Gates table names GraphQL. Both are intentional: the query-count bound came from the critique's N+1 finding and is the requirement, not an implementation note, and the governance gate is defined in those terms by the project. Flagged rather than ticked so the exception stays visible.
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [ ] Success criteria are technology-agnostic (no implementation details) — **qualified**, same reason: SC-005 counts database queries as well as worker requests, because a per-branch read that is one request but 200 queries would satisfy the PRD's wording and still be the N+1 the critique caught.
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- FR-024 (total commit count) was the one open marker. Resolved 2026-09-03 with the PRD author: no total is shown, paging alone. A count since the repository's origin is seldom useful; a count relative to the default branch is a possible later refinement and is listed under Out of Scope. The design canvas badge needs removing.
- The PRD's three other open questions were resolved or deferred without a marker: read-write worker convergence was verified in the current code (see Assumptions); the worktree-protects-commit assumption is stated as an assumption that planning MUST validate (FR-020 stands regardless); the second-request-versus-fan-out choice for the drift column is a planning decision, with the behavioural requirement captured in FR-022.
- The Governance Gates table names GraphQL because the project's "Ask First" gate is defined in those terms; it describes a sign-off obligation, not a design choice.
- All items pass except the two Content Quality items qualified above, which are recorded exceptions rather than omissions. Spec was taken to `/speckit-plan` on that basis.
- **SC-002 and the two-hour figure, reconciled 2026-09-04.** The critique's P3 finding said SC-002 was unmeasurable and was withdrawn on the premise that the two-hour figure is "context, not a target". The `/speckit-analyze` pass then restored the figure, which reads as a reversal. Both are right about different things and the final text reflects that: the two hours is the *baseline being replaced*, stated so the problem has a size, and the criterion it supports is the capability ("self-service in the product"), which is verifiable at ship time. It is not a post-launch KPI with an owner and a measurement window, and nothing in the task list treats it as one.
- **Test-level departures from the PRD**, recorded rather than silent: the PRD names four agreed unit-test targets. The commit log reader and the bounded RPC wait land as component tests because both do real I/O, against a clone and a bus adapter respectively; the pure classification they wrap keeps its unit tests, which is where the behind-versus-rewritten logic the PRD wanted covered actually lives. The git read client gained a unit test (T093) during analysis.
- The PRD's **multi-worker test** is deliberately not built in this slice. Decided 2026-09-04 with the PRD author. The PRD called it the requirement most likely to pass single-worker and fail in production, so the reasoning is recorded rather than implied: the `RefreshGitFetch` fan-out is pre-existing and already load-bearing (the read-write sync uses it every minute, and each git worker declares its own exclusive broadcast queue on the supported driver, see `research.md`), so a two-worker fixture here would re-verify someone else's code. What is new is that per-worker divergence becomes user-visible, and the spec's answer is the freshness statement (SC-009, FR-007). That compensating control is therefore pinned by test: the commit-log suite drives the reader against two clone directories left at different states and asserts the answer tracks the clone being read. **Revisit trigger**: INFP-672 (pinning a repository to a chosen commit). Today a divergent worker causes a wrong display; once a user selects a commit off that list it causes a wrong write, and a freshness stamp stops being an adequate answer.
- Amended 2026-09-04 after `/speckit-analyze`: SC-002 regained the PRD's two-hour Solution Architecture baseline, which had been dropped in the rewrite; SC-014 no longer claims "no restart", which the environment-loaded setting cannot deliver, and now claims no deployment or schedule rewrite, which it does; and `RepositoryCommits.git_ref` became nullable to match the drift type and the `NOT_TRACKED` case.
- Amended 2026-09-03 after the dual-lens critique (`critiques/critique-20260903-1439.md`). FR-004 and SC-005 now bound the database query count as well as the worker request count, User Story 3 gained the row-set rule and a read-only inheritance scenario, and the drift list's row set is stated in Assumptions. The change came from the critique's finding that reusing the periodic sync's per-branch helper would make the branch list an N+1 read.
