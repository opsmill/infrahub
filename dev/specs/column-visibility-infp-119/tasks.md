---
description: "Task list for user-controlled column visibility in list views"
---

# Tasks: User-controlled column visibility in list views

**Input**: Design documents from `dev/specs/column-visibility-infp-119/`

**Prerequisites**: spec.md, plan.md

**Tests**: Included. Constitution IV requires component tests for the user-visible criteria and unit
tests for the pure rules. TDD throughout: each rule and component test was written first and
confirmed failing before its implementation.

**Organization**: Grouped by the order the work was executed. The table seam (Phase 2) is genuinely
independent of everything else. The rules (Phase 1) and the reveal plumbing (Phase 3) touch disjoint
files but are *not* independent: T014 calls the two-argument form of the list-view rules, which only
exists after T004, so T003/T004 ran in the first wave for that reason. Everything touching the UI
waits on the hook, which is the one funnel in the graph.

**Status**: All tasks complete. Recorded after the fact, including the two review rounds and the
bot-review round, because what those rounds changed is the most useful part of the record.

## Conventions & Guardrails

- **No work-item or requirement IDs in source.** Do not write `FR-xxx`, `SC-xxx`, `INFP-119`,
  `IFC-3079`, or task IDs in code, comments, docstrings, or test names
  (`.agents/rules/code-doc-style.md`). They stay in this file, commit messages, and the changelog.
- **No line-number citations in documentation.** Reference `module/path.ts::Symbol`
  (`dev/guidelines/documentation.md`). Line numbers rot; this feature's own docs proved it twice
  before merge — once from a file move, once from a formatter reflow triggered by a rename.
- **No manual memoization.** React Compiler is enabled; `useCallback`, `useMemo` and `React.memo` are
  forbidden in new code.
- **`domain/` stays pure.** No React, no I/O, no runtime table-library import.
- **One owner per URL param.** One hook reads both; never mirror the params into a second store.
- **Empty list means no param.** Every write drops a list that came out empty rather than writing an
  empty one.

## Phase 1 — Foundation (concurrent)

- [x] **T001** Add the two param keys to the QSP map.
- [x] **T002** Declare the `ColumnSurface` vocabulary and the four concrete surfaces. All four mark
  the identity, kind, and actions ids as fixed. `excludeField` polarity is per-surface and the object
  surface is the only one that excludes resource-pool relationships — the shared rule *includes*
  them so their data is fetched, and only the object builder strips their columns.
- [x] **T003** *(RED)* → **T004** *(GREEN)* Reveal opt-in on the two list-view rules: an optional set
  of revealed names that opens the `display: "extra"` gate and only that gate. Every existing caller
  is unaffected because the parameter is optional — nine modules reference the two rules, several
  through default parameters rather than direct calls.
- [x] **T005** *(RED)* → **T006** *(GREEN)* `getColumnCandidates`: schema plus surface to the list the
  picker may offer, deduped, with fixed ids stripped and `canReveal: false` collapsing candidates to
  defaults. No branching on the surface.
- [x] **T007** *(RED)* → **T008** *(GREEN)* `getColumnVisibilityState`: the single trust boundary.
  Drops unknown names, drops entries agreeing with the default, hiding wins on a contradiction, and
  clamps to at least one visible field column. `getRevealedFields` reads the finished state.
- [x] **T009** *(RED)* → **T010** *(GREEN)* `toggleColumn` and `hideColumn`: pure rewrites of the two
  lists. Toggling back to default leaves the field in neither. `hideColumn` never consults the
  candidate list, so the header entry point can write without knowing its surface.

## Phase 2 — The shared table seam (concurrent with Phase 1)

- [x] **T011** *(RED)* → **T012** *(GREEN)* `DataTable` accepts `columnVisibility` and passes it into
  the table state. Seven component tests, no mocks. The most valuable of them asserts the grid track
  count against the visible column count — a phantom track misaligns every row and is otherwise
  invisible.

## Phase 3 — Reveal plumbing, object list only (after T004; concurrent with Phase 2)

- [x] **T013** Builder takes an optional resolved field list; omitted, behavior is unchanged.
- [x] **T014** Revealed names travel into the request through the fetch's existing injectable rule
  overrides.
- [x] **T015** Revealed names join the list cache key through a conditional spread, so a caller that
  reveals nothing hashes exactly as before. The count query needs no equivalent — it selects no
  fields. A guard test asserts a revealed field produces a column definition.

## Phase 4 — The hook (the funnel)

- [x] **T016** `useColumnVisibility`: one `useQueryStates` over both params. Returns the candidates,
  the override map, the revealed names, the ordered field schemas a builder consumes, the departure
  count, and whether either param is present at all. No test of its own — its consumers cover it.

## Phase 5 — UI (after T016)

- [x] **T017** *(RED)* → **T018** *(GREEN)* The checklist: searchable, marks fields carrying an active
  sort or filter and keeps them selectable, disables the last visible column, and offers reset only
  when a param is present. Twenty-four component tests, including every delta-from-default case.
- [x] **T019** The toolbar trigger with a badge counting departures, reveals included.

## Phase 6 — Wiring the four surfaces

- [x] **T020** The table context carries the surface and the capability. Optional props with safe
  defaults, which is what keeps this to three files rather than eleven.
- [x] **T021** The shared toolbar hosts the picker behind the capability.
- [x] **T022** Object list: all three reveal legs plus the override map.
- [x] **T023** Both IPAM tables: the override map only. Builders and column-order constants untouched.
  The two edits are kept identical so a reviewer sees any divergence.
- [x] **T024** Relationship tables: a one-control toolbar row rendered from inside the table, taking
  the schema as a prop, because two of its three hosts provide no context at all. Read-only headers
  are left read-only.

## Phase 7 — The header entry point

- [x] **T025** *(RED)* Update the exact-array assertion on the header menu, which pins the item order.
- [x] **T026** *(GREEN)* A hide action after the filter entry, gated on the capability, owning its own
  separator so gating it off leaves no dangling rule.

## Phase 8 — Coverage and documentation

- [x] **T027** One E2E: a pasted link hides the column, the picker restores it, and the param leaves
  the URL. Asserts real row content, because a header-only assertion passes on a crashed table body.
  Exact matching is load-bearing — the demo schema carries a second attribute whose label contains
  the first's.
- [x] **T028** `dev/knowledge/frontend/column-visibility.md` records the decisions whose reasoning is
  not recoverable from the code.
- [x] **T029** Changelog fragment.

## Phase 9 — First review round

- [x] **T030** The header's hide action resolved the default surface while the hook writes back
  *validated* lists, so hiding a second column on an IPAM table erased the first. Fixed by reading the
  surface from context through a non-throwing accessor.
- [x] **T031** The grid template emitted `repeat(0, …)` once only the identity and actions columns
  remained; the CSSOM rejects that outright and every row split in two. Guarded, with a boundary test.
- [x] **T032** Two layering violations, each the only instance in the repo: a model importing rules,
  and a domain module importing the table library. Split and re-declared.
- [x] **T033** `getRevealedFields` widened, then in the second round narrowed again to take the
  finished state — the first fix removed the duplicated enforcement but left the state derived twice.
- [x] **T034** An inert param left by a kind switch hid the reset control. Reset now keys off the raw
  params, which is a different question from the badge's count.

## Phase 10 — Second review round

- [x] **T035** Both entry points appeared on tables that cannot honour them — the role-management
  pages, then Proposed Changes, which passes a schema to its headers purely for sorting and renders
  no data table. The third instance of one class; replaced two ad-hoc gates with one capability.
- [x] **T036** Hiding every column split the IPAM availability rows, whose identity cell spans a track
  that the two-column case does not have. Clamped in the trust boundary rather than patched per cell.
- [x] **T037** A hide belonging to another kind was silently destroyed on the next write. The kind
  switcher already pruned filters the new schema lacks; the column params now prune beside them.
- [x] **T038** Quality: an options object for the builder, the unused surface identifier removed, the
  relationship surface expressed as its one difference from the object surface, `FieldSchema` declared
  once, and three renames — candidates named for what they are.

## Phase 11 — Bot review round

- [x] **T039** `in` reads walked the prototype chain, so a field named `constructor` read as visible.
  Two sites, and the reported one was the less important: the same read in the clamp can defeat the
  one-visible-column guarantee. The reported repro does not actually fail — hiding a default-*visible*
  field of that name creates a real own key.
- [x] **T040** Re-selecting the kind already in view cleared the params for no reason.
- [x] **T041** Nine comment sites brought into line with the code-documentation rule: no naming other
  code, no narrating the rejected approach, one sentence for a why. The rationale moved to the
  knowledge page, which is where the rule says a paragraph belongs.
- [x] **T042** Forty-six line-number citations converted to symbol references, every symbol verified
  to resolve. One of them survived a concurrent edit to the very comment it cited.
- [x] **T043** A relationship-table regression test. Writing it found the case that actually pins the
  surface: hiding every field while revealing an extra one. Under the wrong surface the revealed field
  satisfies the clamp and every field column vanishes. A bare reveal proves nothing there, because
  that table builds default columns and the library ignores a visibility key with no column.
- [x] **T044** One rejected finding: the claim that the shared table ignores visibility when
  collecting headers. It does not — the library's header groups depend on the visible leaf columns.
  Answered in-thread with the library source, three passing tests, and a browser check, rather than
  changing working code.

## Follow-ups to file

1. Column reordering — promised on the ticket.
2. Unify the three column builders. Prerequisite: IPAM component tests.
3. Align IPAM attribute filtering to the object rule. Removes currently-visible columns, so it needs
   product sign-off.
4. Durable per-user preferences through the backend `preferences` entity.
5. Wire the five role-management tables, then drop the capability opt-in.
6. Reveal on relationship tabs — needs an injectable seam in the relationships fetch.
7. A semantic Tailwind token layer. The styling guideline recommends tokens this codebase does not
   have, so the guideline is currently unfollowable.
8. An E2E for the reveal path, asserting non-empty cells.
9. The IPAM address relationship rule prepends a field without removing it from the list it then
   spreads. It does not duplicate today only because the shared rule drops that field's kind.
