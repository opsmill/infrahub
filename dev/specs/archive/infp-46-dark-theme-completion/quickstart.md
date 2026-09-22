# Quickstart: Dark Theme Completion

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

How to set the work up and how to verify each user story. Written to be usable before any of the
implementation exists.

## Prerequisites

```bash
git submodule update --init frontend/packages/schema-visualizer
```

Required for User Story 7, and it also clears the two phantom `betterer` findings an uninitialised
submodule produces in a fresh worktree.

```bash
uv pip install -e python_sdk
```

Fresh worktrees skip building the editable SDK, and `infrahub_sdk` imports fail without this.

### Branch base — this is a stacked PR

The branch is based on `bab-dark-theme-app` (PR
[#10284](https://github.com/opsmill/infrahub/pull/10284)) and the pull request **targets that
branch**, not `develop`. That puts the surfaces User Story 5 migrates actually in the tree and keeps
this review free of #10284's 151 files.

```bash
git fetch origin bab-dark-theme-app && git rebase origin/bab-dark-theme-app
```

Re-target `develop` once #10284 merges; rebase again if it is revised. ⚠ #10284's failing end-to-end
checks are inherited by this pull request — say so in the description so reviewers do not read them
as caused by this work.

## Verification commands

⚠ `pnpm test` and the other `pnpm` scripts abort before running in this environment. Call the
binaries directly.

```bash
cd frontend/app && node_modules/.bin/vitest run
```

```bash
cd frontend/app && node_modules/.bin/biome ci .
```

```bash
cd frontend/app && node_modules/.bin/tsc --noEmit
```

```bash
cd frontend/app && node_modules/.bin/betterer ci
```

Backend:

```bash
uv run invoke backend.test-unit
```

After changing the GraphQL schema or config model, regenerate and commit — CI fails on stale
generated files:

```bash
uv run invoke schema.generate-graphqlschema && uv run invoke schema.generate-jsonschema
```

```bash
cd frontend/app && pnpm codegen
```

## Manual verification by user story

Run the stack, then walk each story. The theme class lands on the document element, so the fastest
sanity check throughout is the browser console:

```js
document.documentElement.classList.contains("dark")
```

### US1 — Choose a theme

1. Sign in, open preferences. The theme field shows the flag's default with a source note
   distinguishing it from a personal choice.
2. The dark option carries a visible **"alpha"** tag.
3. Select dark — the interface repaints with no reload.
4. Reload. It is dark **in the first painted frame**. To check honestly, throttle the network hard
   (DevTools → Network → Slow 3G) so the preference query is visibly slow: a correct implementation
   still paints dark immediately, a broken one shows light and flips.
5. Sign in from a second browser: dark there too.
6. Select "match system", then switch the operating system's appearance with the page open — the
   interface follows without a reload.
7. Clear your choice back to the inherited default and confirm the source note reverts to reporting a
   default rather than your own preference.
8. ⚠ Confirm there is **no** theme field on the organisation-wide preferences form — theme is
   user-scoped in this version.

### US2 — The feature flag

1. With `INFRAHUB_EXPERIMENTAL_DARK_THEME` on (the dev stack default) and **no** stored theme, load
   the app: dark. Set your operating system to light and reload — still dark. The default ignores the
   system deliberately, or an engineer on a light machine would never dogfood it.
2. Confirm `GET /api/config` reports `experimental_features.dark_theme: true`, unauthenticated, with
   no version disclosed.
3. Turn the flag off, restart, reload: light, **and the theme field is gone from preferences** — not
   merely reduced to light. Check "match system" is absent too; leaving it would be a hole straight
   through the flag for anyone on a dark operating system.
4. With the flag off, confirm a previously stored `DARK` preference is **still in the database** —
   ignored, not deleted. Turn the flag back on and confirm that user is dark again.
5. Clear browser storage, set the operating system to **dark**, and reload with the flag on: the
   first paint is **light**, then corrects to dark. Both halves matter — light because the pre-paint
   script runs before it knows whether the flag is even on, and the correction because the flag's
   default is dark.

### US3 — GraphQL sandbox

1. In dark, open the GraphQL sandbox: it renders dark.
2. Change the theme in another tab or via preferences: the sandbox follows.
3. Confirm GraphiQL's **own** theme picker is absent from its settings dialog — with `forcedTheme`
   set, GraphiQL hides it, which is the intended single source of truth.
4. In light, confirm it is unchanged from today.

### US4 — Mermaid diagrams

1. In dark, open content containing a Mermaid diagram. Both the diagram palette and the container
   behind it are dark — the `bg-white` wrapper is the usual culprit if the diagram looks correct but
   sits on a bright panel.
2. Switch the theme with the diagram on screen: it re-renders to match.
3. ⚠ Watch the console and the React profiler while doing this. The plugin array must be memoised on
   the resolved theme; if it is rebuilt every render the pipeline re-runs continuously and the
   diagram flickers or the page pins a CPU core.
4. Render a deliberately invalid diagram and confirm the error banner is legible in both themes.

### US5 — Token discipline

1. In dark, walk the proposed-changes flow, a diff view, the checks view and path traversal. No
   bright surface, and borders and text match the rest of the interface.
2. Confirm no application component paints a fixed surface palette:

   ```bash
   git grep -nP '(?<!dark:)\bbg-(white|gray-(50|100))\b' -- 'frontend/app/src/**/*.tsx'
   ```

   Expect no output. ⚠ `-P`, not `-E`: git's ERE does not implement `\b` on every platform, and
   where it does not, the pattern matches *nothing* — the check passes while seeing no files at
   all. ⚠ The lookbehind is what makes the empty result meaningful: `dark:bg-white/5` and friends
   are legitimate translucent overlays, and without excluding them this reports five standing
   false positives. Counting `dark:` occurrences is the wrong metric in both directions: a `dark:`
   variant renders correctly (merely unmaintainable, and legitimate for categorical ramps and
   asset swaps), while the files that are actually broken carry no variant at all — the defect is
   the *absence* of one on a fixed palette. ⚠ `rtk` reformats grep output and an empty piped
   result is not proof — run this through plain `git grep`.
3. In light, compare the same pages against the pre-change build: no visual difference.

### US6 — Data viewer

1. In dark, open the data viewer beside another dark surface: the greys belong to the same family.
   The tell is `neutral` (cold) against the theme's `stone` (warm).
2. Exercise each content type the viewer handles. None shows a fixed light background — two `bg-white`
   containers exist today.

### US7 — Schema visualizer

1. Upstream first: dark support merged and released in `opsmill/infrahub-schema-visualizer`.
2. Here: bump the pointer, then in dark open the visualizer and confirm canvas, nodes, edges, labels
   and controls are dark and legible.
3. ⚠ Never move the submodule pointer to an unpushed commit — it breaks every other checkout.
4. Confirm no visualizer styling code landed in this repository.

## Regression watch

- **Light theme unchanged (FR-020, SC-005)** is the constraint most easily broken by a careless token
  swap. Compare light-theme rendering before and after on every page touched.
- **Contrast (FR-021)** — text and essential interface elements must stay legible against their
  surfaces in dark, at the level light already achieves.
- **Semantic colors are out of scope** — status, severity, diff conflict, danger palettes are tracked
  separately. Do not redesign them here; do not let a mechanical token swap flatten two distinct
  severities into one either. `shared/components/ui/badge.tsx` carries the most of these.
- **End-to-end suites** pin the theme explicitly rather than inheriting the flag's value, so they
  stay deterministic. ⚠ #10284's end-to-end checks are already failing and are out of scope — do not
  read those failures as fallout from this work; establish the baseline from a green run after it
  lands.
