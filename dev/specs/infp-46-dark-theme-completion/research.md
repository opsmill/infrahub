# Research: Dark Theme Completion

**Feature**: [spec.md](./spec.md) | **Date**: 2026-08-17

Phase 0 output. Each section states an open question from the spec, the options considered, the
decision, and the evidence gathered from the codebase. Findings marked **⚠** are traps that would
cost a rewrite if discovered during implementation.

## R1 — How is "non-production build" detected? (FR-010, FR-011, FR-012)

**Question**: The handover note called this "make canary enabled by default". No `canary` concept
exists anywhere in the repository, so the mechanism had to be chosen rather than located.

### Options considered

| Option | Verdict |
|---|---|
| New `ExperimentalFeaturesSettings` flag | Rejected as the primary mechanism |
| `installation_type` | Rejected — wrong axis |
| Frontend build-time environment variable | Rejected |
| PEP 440 pre-release detection on the running version | **Chosen** |

**`installation_type` is the wrong axis.** `backend/infrahub/constants/environment.py` defines
`INSTALLATION_TYPE = "community"`. It distinguishes community from enterprise, not production from
non-production. It is already on the config payload, which makes it a tempting false lead. ⚠

**A frontend build-time variable is wrong** because it is baked at asset-build time. A locally built
image deployed into a production-like environment would still claim non-production, and the same
published assets are served by every deployment.

**An experimental flag alone is wrong** because it requires every non-production deployment to be
configured individually — which is exactly the per-engineer setup burden SC-008 exists to avoid.

### Decision

Derive the default from the running version's PEP 440 pre-release status, with an explicit operator
override retained on top.

Versions come from `hatch-vcs` (`pyproject.toml`: `git_describe_command = ["git", "describe",
"--tags", "--long", "--match", "infrahub-v*"]`, generating `backend/infrahub/_version.py`) — the
INFP-566 dynamic-versions work. Verified against the running build:

| Version | `is_prerelease` | Default theme |
|---|---|---|
| `1.11.0b2.dev134+geb5acb009` (this checkout) | `True` | dark |
| `1.12.0.dev5+g1a2b3c` (dev build) | `True` | dark |
| `1.11.0b2` (beta) | `True` | dark |
| `1.11.1rc1` (release candidate) | `True` | dark |
| `1.11.0` (release) | `False` | **system** |

The production default is `system` rather than a fixed palette — specified directly by the requester.
A deployment with no opinion about a particular user defers to that user's browser setting; only
non-production overrides that, deliberately, so the team sees dark whatever their operating system
says. The trade this accepts is recorded in the spec's Assumptions: on production, a user whose
system is dark reaches the alpha palette without explicitly choosing it.

This needs no configuration for the common case: every build the team runs day to day carries a
`.devN`/`bN`/`rcN` segment, and every published release does not. The operator override (FR-012)
remains available for the deployment that wants to disagree.

### ⚠ The frontend must not do this detection

`backend/infrahub/api/internal.py` exposes two endpoints with different auth postures:

- `GET /api/config` — **unauthenticated**. Carries `experimental_features`, `installation_type`, sso,
  ldap, policy.
- `GET /api/info` — **authenticated** (`Depends(get_current_user)`). Carries `deployment_id` and
  `version`.

The version is only on the authenticated endpoint, but the login page needs a theme *before* there is
a session (spec edge case "Before sign-in"). Therefore the backend computes the default and publishes
the **result** on the unauthenticated config payload. The frontend never parses a version string, and
no version information is newly exposed to anonymous callers — only a resolved `light`/`dark` value.

## R2 — How is the flash of the wrong theme prevented? (FR-006, SC-002)

**Question**: The preference is account-backed and fetched asynchronously. A naive implementation
paints light, then repaints dark once the query resolves.

### Evidence

`frontend/app/index.html` is a plain SPA shell: `<html lang="en" class="h-full">`, `<div id="root">`,
and a module script. `frontend/app/src/main.tsx` is a bare `createRoot(...).render(<App />)`. There
is no server-side rendering and no template interpolation at serve time — the same static assets are
served to every deployment.

### Decision

A synchronous, render-blocking classification script inline in `<head>`, before the module script,
which sets the theme class on the document element from a `localStorage` mirror. React never owns
the first paint decision.

The mirror is written whenever the effective theme resolves (from the account preference, or from the
deployment default on the config payload). Precedence inside the inline script:

1. Mirrored resolved theme, if present.
2. Mirrored raw choice of "system" → resolve against `prefers-color-scheme` at that instant.
3. Nothing mirrored → resolve against `prefers-color-scheme`.

**Step 3 is why the cold start is correct, not merely tolerable.** Because the production deployment
default is itself `system`, an empty cache and a populated one give the same answer for a
never-visited production deployment — the fallback and the authoritative value agree instead of
fighting. An earlier draft defaulted step 3 to light and accepted a first-visit flash as a scope
boundary; making the production default `system` removes that case rather than tolerating it.

**Residual case**: a *non-production* deployment on a light system. The script paints light from the
system setting, then flips to dark when the config payload arrives. This affects the team's own
builds only, and eliminating it would require the server to template the shell — disproportionate.

**Reconciliation**: when the authoritative preference disagrees with the mirror, the class is updated
and the mirror rewritten.

Cross-tab synchronisation is **out of scope** — a second tab picks up a change on its next load. The
mirror would make a `storage`-event implementation nearly free, so this is a deliberate deferral
rather than a limitation of the design.

## R3 — How is the GraphQL sandbox bound? (FR-014)

**Question**: `frontend/app/src/pages/graphql/index.tsx:24` passes `forcedTheme="light"`.

### Evidence

From the installed `graphiql@5.2.4` sidebar implementation:

```ts
const THEMES = ['light', 'dark', 'system'] as const;
forcedTheme?: (typeof THEMES)[number];

useEffect(() => {
  if (forcedTheme === 'system') setTheme(null);
  else if (forcedTheme === 'light' || forcedTheme === 'dark') setTheme(forcedTheme);
}, [forcedTheme, setTheme]);
```

Three facts follow. The prop is reactive, so a changing value propagates without remounting. When
`forcedTheme` is set, GraphiQL hides its own theme picker (`{!forcedTheme && …}`) — desirable, since
the application setting becomes the single source of truth. And GraphiQL persists its own theme in
its storage, which `setTheme` overwrites.

### Decision

Pass the application's **resolved** theme (`"light"` or `"dark"`), never `"system"`.

⚠ Passing `"system"` would make GraphiQL run its own `prefers-color-scheme` resolution independently
of the application's. A user on "match system" whose application resolved to dark would be correct
only by coincidence, and would diverge from an organisation default or an explicit choice. Resolving
once, in the application, and handing down the answer is the only binding that cannot drift.

## R4 — How are Mermaid diagrams bound? (FR-015)

**Question**: `markdown-with-mermaid.tsx:11` pins `mermaidConfig: { theme: "default" }`.

### Evidence

The file uses `strategy: "inline-svg"`, so diagrams are rendered client-side in the browser and a
theme change can re-render them without a build step. Three obstacles are visible in the source:

1. ⚠ **`rehypePlugins` is a module-level constant.** Making it theme-dependent means constructing it
   per render. A new array identity on every render re-runs the rehype pipeline continuously — the
   plugin array must be memoised on the resolved theme, and nothing else.
2. **`mermaid-diagram.tsx` hardcodes `className="relative bg-white"`** on the pan/zoom container.
   This is the bright panel behind an otherwise dark diagram, independent of the diagram's own
   palette.
3. **The parse-error fallback** builds a `mermaid-error` element. FR-015 requires that state legible
   in both themes, so its styling must be tokenised alongside the container.

### Decision

Derive `mermaidConfig.theme` from the resolved application theme, mapping to Mermaid's built-in
`"dark"` and `"default"`. Memoise the plugin array on the resolved theme. Tokenise the container
background and the error banner.

Mermaid's own `"neutral"` and `"forest"` themes are not used: the warm palette is not reproducible in
Mermaid's built-ins, and matching it precisely would mean a hand-authored theme-variables object —
disproportionate for the first pass, and a reasonable later refinement.

## R5 — How does the theme preference join the existing store? (FR-001 → FR-004)

**Question**: whether to extend the existing preference machinery or add separate storage.

### Evidence

The existing machinery is a complete two-layer implementation, and theme is structurally identical to
`date_format` — a small closed set of keys, nullable, resolved user → global → default.

Backend:

- `backend/infrahub/core/preferences/constants.py` — `DateFormat`, `PreferenceSource`,
  `GLOBAL_OWNER_ID`, `PREFERENCE_LOCK_NAMESPACE`.
- `backend/infrahub/core/preferences/models.py` — `Preference(StandardNode)` with `owner_id`,
  `date_format`, `timezone`; plus `ResolvedPreference[T]` and `EffectivePreferences`.
- `backend/infrahub/core/preferences/repository.py`, `permissions.py`.
- `backend/infrahub/graphql/types/preferences.py` — enums built with `Enum.from_enum`, and one
  `Effective…` `ObjectType` per field carrying `value` + `source`.
- `backend/infrahub/graphql/queries/preferences.py`, `backend/infrahub/graphql/mutations/preferences.py`.

Frontend:

- `entities/preferences/domain/model/preference.ts` — `PreferenceValues`, `EffectivePreferences`.
- `entities/preferences/ui/preference-fields.tsx` — `Combobox` fields, source tooltips, and the
  `EMPTY_VALUE_LABEL = "Automatic (inherited)"` convention for "no override".
- `entities/preferences/ui/{preferences-form,global-preferences-form,user-preferences-card}.tsx`.

### Decision

Extend. Adding a `Theme` enum and a nullable `theme` field mirrors `date_format` end to end, and
inherits resolution, source reporting, the global/user split, permissions and locking without new
concepts.

⚠ Two constraints are documented in the existing source and must be carried:

- `models.py` states persisted nullable fields must be written `Optional[X]`, **not** `X | None`,
  because of how `StandardNode.guess_field_type` works. Python 3.14 has not lifted this.
- `types/preferences.py` states enum descriptions must stay on a single line, because
  `graphql-core`'s SDL printer dedents multi-line descriptions inconsistently across versions and
  makes the generated `schema/schema.graphql` environment-dependent.

### ⚠ Open governance point

`AGENTS.md` lists "Database schema or migration changes" and "GraphQL schema modifications" under
**Ask First**. `Preference` is a `StandardNode`, so adding a nullable field is additive — existing
rows simply lack the property and read as `None`, which is already the "nothing set" case. No data
migration is expected. The GraphQL schema does change (new enum, new field on the effective-preferences
type, new mutation input), and `schema/schema.graphql` is generated and CI-validated. Both points are
flagged for explicit human sign-off before implementation, not assumed.

## R6 — Token migration surface (FR-017, FR-018, SC-004)

### Evidence

`frontend/packages/ui/src/styles/theme.css` defines 104 custom properties on `:root` with a `.dark`
block at line 60. The light palette is **warm** — `--background: var(--color-stone-100)`,
`--foreground: var(--color-stone-800)`, `--card`/`--panel` built from `stone`/`gray` stops.

`shared/components/data-viewer/data-viewer.tsx` uses `bg-neutral-800 text-neutral-200` (line 29),
`border-neutral-700` (line 77) and two `bg-white` containers (lines 58, 89). `neutral` is Tailwind's
cold grey; `stone` is the warm one. This is precisely the reported tone mismatch, and the two
`bg-white` panels are a fixed light background in dark mode, which FR-018 forbids.

Counted on the PR #10284 branch, roughly twenty application files still carry hardcoded `dark:`
variants, concentrated in `entities/diff/` (node-diff, checks, conflicts, badges),
`entities/path-traversal/`, `entities/proposed-changes/`, `entities/tasks/`, and
`shared/components/ui/badge.tsx` (twelve occurrences, the single largest).

### Decision

Migrate to tokens, and add an automated guard so SC-004 holds as a standing property rather than a
one-time cleanup. Without a guard the debt returns with the next feature branch, and SC-004's wording
("holds as a standing property") would be unenforceable. The concrete guard mechanism — a lint rule
versus a `betterer` counter — is left to the plan; `betterer` is already wired into CI here.

`shared/components/ui/badge.tsx` is called out separately: at twelve occurrences it likely encodes
semantic colors (status, severity). **Redesigning semantic palettes is out of scope** — that is the
separately-tracked "content that carries its own colors" work. The instruction here is narrower and
easier to get wrong in the opposite direction: migrate it without *degrading* what exists. Where a
mechanical token swap would flatten two currently-distinct severities into one, leave the distinction
in place and note it for the separate effort rather than collapsing it.

## R7 — Schema visualizer (FR-016)

### Evidence

`git submodule status frontend/packages/schema-visualizer` reports
`-f7d3cc5af409e9db7916947e33b887737a626d4d` — the leading `-` means **uninitialised**, and the
directory is empty in this worktree. The package is consumed as `infrahub-schema-visualizer` from
`frontend/packages/schema-visualizer`.

`AGENTS.md` is explicit: a submodule pointer must not move to an unpushed commit, because that
breaks every other checkout. The upstream change must be merged before the pointer bump lands here.

### Decision

Two deliverables in strict order: an upstream pull request against
`opsmill/infrahub-schema-visualizer` implementing dark support and accepting the embedding
application's theme; then a pointer bump here. No visualizer styling code lands in this repository.

This is the reason User Story 7 is P3 and last: it is the only item whose completion is gated on a
merge in another repository, and nothing else depends on it.

⚠ `git submodule update --init frontend/packages/schema-visualizer` is a prerequisite for any work on
this item, and also removes the two phantom `betterer` findings that an uninitialised submodule
produces in a fresh worktree.

## R8 — Test and verification impact

Changing the default theme on non-production builds (FR-010) changes what the end-to-end suites see,
since they run against locally built — therefore pre-release — versions.

Both suites are affected: the legacy Playwright suite (`frontend/app`, `pnpm test:e2e`) and the
pytest/testcontainers suite (`tests/e2e`). Any assertion on a specific color, and any screenshot
comparison, may flip.

**Decision**: end-to-end runs pin the theme explicitly rather than inheriting the build-derived
default, so the suites remain deterministic and independent of the version they happen to be built
at. This also keeps them from silently masking a regression in the default-resolution logic, which
gets its own targeted coverage instead.

⚠ PR #10284's end-to-end checks are already failing and are out of scope. Their failures must not be
conflated with fallout from this change; the baseline needs to be established from a green run after
#10284 lands.

Local verification runs the binaries directly rather than through `pnpm` scripts, which abort in this
environment: `node_modules/.bin/{vitest,biome,tsc,betterer}`.
