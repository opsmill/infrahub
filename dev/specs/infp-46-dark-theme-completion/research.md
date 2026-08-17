# Research: Dark Theme Completion

**Feature**: [spec.md](./spec.md) | **Date**: 2026-08-17

Phase 0 output. Each section states an open question from the spec, the options considered, the
decision, and the evidence gathered from the codebase. Findings marked **⚠** are traps that would
cost a rewrite if discovered during implementation.

## R1 — How is the dogfooding deployment gated? (FR-010, FR-011, FR-012, FR-013)

**Question**: The handover note called this "make canary enabled by default". No `canary` concept
exists anywhere in the repository, so the mechanism had to be chosen rather than located.

### Options considered

| Option | Verdict |
|---|---|
| An `ExperimentalFeaturesSettings` flag, following the existing convention | **Chosen** |
| PEP 440 pre-release detection on the running version | Considered at length, then rejected |
| `installation_type` | Rejected — wrong axis |
| Frontend build-time environment variable | Rejected |

**`installation_type` is the wrong axis.** `backend/infrahub/constants/environment.py` defines
`INSTALLATION_TYPE = "community"`. It distinguishes community from enterprise, not production from
non-production. It is already on the config payload, which makes it a tempting false lead. ⚠

**A frontend build-time variable is wrong** because it is baked at asset-build time. A locally built
image deployed into a production-like environment would still claim non-production, and the same
published assets are served by every deployment.

### Decision

Add `dark_theme: bool = False` to `ExperimentalFeaturesSettings` and enable it in the development
stack's compose configuration.

The codebase already has this pattern, twice, and both instances default to off with a per-deployment
env override:

```yaml
INFRAHUB_EXPERIMENTAL_GRAPHQL_ENUMS: ${INFRAHUB_EXPERIMENTAL_GRAPHQL_ENUMS:-false}
INFRAHUB_EXPERIMENTAL_VALUE_DB_INDEX: ${INFRAHUB_EXPERIMENTAL_VALUE_DB_INDEX:-false}
```

`experimental_features` is already on the unauthenticated `/api/config` payload, so the flag is
readable before sign-in with no new field and no new endpoint.

### Why the version-derived design was withdrawn

It was specified first, and in detail. Versions come from `hatch-vcs` (`pyproject.toml`:
`git_describe_command = [..., "--match", "infrahub-v*"]`, generating `backend/infrahub/_version.py`)
— the INFP-566 dynamic-versions work. The derivation was verified against real builds:

| Version | `is_prerelease` |
|---|---|
| `1.11.0b2.dev134+geb5acb009` (this checkout) | `True` |
| `1.12.0.dev5+g1a2b3c` (dev build) | `True` |
| `1.11.1rc1` (release candidate) | `True` |
| `1.11.0` (release) | `False` |

It worked, and it needed no configuration. It was rejected anyway, for two reasons:

1. **It gates on the wrong thing.** "Pre-release" is a property of a *version*, not of a deployment.
   A customer running `1.11.0rc1` in their own staging environment matches it exactly — and they are
   not "the deployments we run". The flag targets deployments directly, which is what was meant.
2. **It invents a mechanism where one exists.** The repository already has a convention for exactly
   this, used by both existing experimental settings. Deriving a bespoke default from version strings
   is more machinery doing the same job less precisely.

⚠ The rejected design also required parsing PEP 440 versions in the backend. The chosen design needs
none, so this feature introduces **no new dependency** — one fewer governance gate crossed.

Withdrawing it removed a resolver module, the version parsing, a config field, and five tasks.

### The accepted trade

The flag only reaches deployments whose configuration this repository controls. A deployment started
some other way — a shared staging box, a cloud instance — stays light until someone sets the env var
there. The version-derived design would have covered those automatically. This was raised explicitly
and the trade accepted: the deployments the team actually runs come from these compose files.

### What the flag governs

While dark is alpha the flag decides both *whether the feature exists* and, where it does, *that dark
is the default*. Compressing two jobs into one switch is deliberate: they separate at the moment the
flag is removed, when the production default becomes its own decision.

⚠ With the flag off the theme field is hidden **entirely**, not reduced to a light-only picker.
Offering "light" and "match system" would leave a hole straight through the gate — a user on a dark
operating system selects match-system and reaches the alpha palette anyway.

⚠ Flipping the flag off must **ignore** a stored `DARK` preference, never delete it. A configuration
change that destroys user data is a much worse failure than a theme that reverts.

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
flag's default). Precedence inside the inline script:

1. Mirrored resolved theme, if present.
2. Mirrored raw choice of "system" → resolve against `prefers-color-scheme` at that instant.
3. Nothing mirrored → light.

⚠ **Step 3 is light, not `prefers-color-scheme`.** The script runs before the config payload arrives,
so it cannot know whether the flag is even on. Guessing from the operating system would put a dark-OS
user into the alpha palette on a deployment where the feature is switched off entirely. Where the
flag is off, light is also the final answer, so this fallback is correct rather than merely safe.

**Known and accepted limitation**: on a browser's *first ever* visit to a **flag-enabled**
deployment, nothing is mirrored, so the first paint is light and corrects to dark once the config
payload arrives. Every subsequent load is correct from the first frame. Eliminating even that one
frame would require the server to template the HTML shell, which is disproportionate for a case
affecting flag-enabled deployments only. Recorded as a deliberate boundary, not an oversight.

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

Enabling the flag (FR-010) changes what the end-to-end suites see, since they run against the
repository's own compose configuration — the same place the flag is switched on.

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
