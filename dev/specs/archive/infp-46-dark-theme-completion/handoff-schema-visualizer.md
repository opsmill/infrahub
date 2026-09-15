# Handoff: dark theme for the schema visualizer (Phase 9, T052–T055)

Self-contained brief for a fresh session. Everything below was verified against the code on
2026-08-18; re-verify anything load-bearing before acting on it.

## The task

Four tasks from [tasks.md](./tasks.md), Phase 9 (US7):

- **T052** — Open a PR on `opsmill/infrahub-schema-visualizer` adding dark support: canvas, nodes,
  edges, labels and controls, **with the theme accepted from the embedding application rather than
  detected independently** (no `matchMedia`, no OS detection inside the package).
- **T053** — Get it merged and released upstream.
- **T054** — Bump the submodule pointer in `opsmill/infrahub` and pass the resolved theme in.
  ⚠ Never point the submodule at an unpushed commit — it breaks every other checkout.
- **T055** — Confirm no visualizer styling code landed in the infrahub repo (FR-016).

## Where the code lives

- Upstream repo: `https://github.com/opsmill/infrahub-schema-visualizer`.
- Vendored in infrahub as a git submodule at `frontend/packages/schema-visualizer/`
  (pointer at the time of writing: `f7d3cc5af`). Fresh worktrees leave it **uninitialized**
  (`git submodule update --init frontend/packages/schema-visualizer`); while uninitialized,
  `betterer ci` in `frontend/app` reports 2 phantom TS issues — that's the known cause, not a
  regression.
- The infrahub app consumes it as a pnpm workspace package (`"infrahub-schema-visualizer":
  "workspace:*"`), imported by exactly two files:
  - `frontend/app/src/pages/schema/graph.tsx` (the `/schema` graph page — main embed)
  - `frontend/app/src/entities/path-traversal/ui/path-flow-graph.tsx` (utility imports)
- The package has its own `AGENTS.md` and `guidelines/` (naming, typescript, styling,
  component-patterns). Notable: **tab indentation** (biome), exports only via root `index.ts`,
  must not depend on `frontend/app` internals, and component files must stay Node-API-free.

## The two builds — this is the crux

The package renders in two hosts with different styling pipelines:

1. **Inside the infrahub app.** The package ships **no CSS** to the app. Instead the app's
   Tailwind build scans the package source and generates its utilities:
   `frontend/app/src/app/styles/index.css` line ~8:
   `@source "../../../../packages/schema-visualizer/src/**/*.{js,ts,jsx,tsx}";`
   Consequence: any class the package uses is compiled with the **app's** Tailwind config —
   including the app's `@custom-variant dark (&:where(.dark, .dark *))` in
   `frontend/packages/ui/src/styles/theme.css`.
2. **The VS Code webview** (`vite.config.webview.ts` + `src/webview.css`). `webview.css` is the
   standalone theming hook: it does `@import "tailwindcss"` and then hand-maintains a set of
   fallback utilities **in hex** under `.schema-visualizer-root` (scrollbars, hovers, shadows,
   focus rings — all light-only today). Any dark strategy must work here too, without the app.

## Current state of the package (surveyed, exact)

- **Zero `dark:` variants anywhere.** Fully light-hardcoded.
- ~137 fixed-palette utility usages, heavily concentrated:
  `text-gray-600` ×34, `text-gray-500` ×27, `bg-gray-100` ×26, `text-gray-400` ×24,
  `text-gray-700` ×20, `border-gray-200` ×13, `border-gray-100` ×12, `bg-white` ×10,
  plus indigo actives (`text-indigo-600`, `bg-indigo-600`, `border-indigo-500`…) and a tail of
  one-offs.
- **Semantic hex palette** in `src/utils/schema-to-flow.ts` (`getEdgeColorForType`):
  `#009966` generics + inherited edges, `#7F22FE` profiles, `#F54900` templates, `#087895` nodes.
  The same hexes are duplicated as arbitrary classes in `src/components/panels/legend-panel.tsx`
  (`bg-[#087895]` etc.) — edge colors and legend swatches must stay in lockstep.
- **ReactFlow** (`@xyflow/react` v12) in `src/components/graph/schema-visualizer.tsx` does **not**
  set `colorMode`. v12 has a `colorMode: "light" | "dark"` prop that themes React Flow's own
  chrome (controls, minimap, selection, attribution) — use it rather than restyling that chrome
  by hand. The dotted `<Background>` also needs a dark-legible color.
- `webview.css` sets light hex `color`/`background-color` on `.schema-visualizer-root` and light
  scrollbar colors.

## Design constraints already decided (in spec.md / by the user)

- Theme comes **from the embedder**. In the app that's a prop; in VS Code the webview entry may
  map VS Code's own theme class (`body.vscode-dark`) to the package's dark state — that counts as
  "from the embedder".
- The app side will pass the resolved theme from
  `frontend/app/src/shared/hooks/use-resolved-theme.ts` (`useResolvedTheme()` — a
  `useSyncExternalStore` over a MutationObserver on the document element's class). It re-renders
  on toggle, so the graph re-themes live.
- FR-016: no visualizer styling lands in the infrahub repo. Tokens/variants for the package live
  **in the package**.
- Dark palette direction in the app is warm (stone-based, `--background: black`,
  surfaces `stone-800/900`, `white/5..10` tints). The visualizer should harmonize, not match
  token-for-token.

## Recommended approach (weighed, not yet reviewed by the user)

Add a `theme?: "light" | "dark"` prop (default `"light"`) to `SchemaVisualizer`:

- Drives `colorMode` on `<ReactFlow>`.
- Sets a marker class (e.g. `sv-dark`) or `data-theme="dark"` on the package's root container.
- Package defines its **own** small token layer in a package CSS file — light values on the root
  container, dark overrides under the marker — and components use those tokens
  (Tailwind 4 `bg-(--sv-surface)` arbitrary-value syntax compiles fine under the app's `@source`
  scan). Both the app build and `webview.css` import the same token file.

Why not plain `dark:` variants keyed on the app's `.dark`: it silently couples the package to the
app's `@custom-variant`, which the app plans to delete once fully tokenized (T027 in tasks.md),
and it does nothing for the webview build. Self-contained tokens satisfy both hosts and FR-016.
If the fresh session finds a simpler path that keeps both hosts working, take it — but keep the
"no independent detection" rule absolute.

For the hex semantic palette (edges/legend): these are categorical colors, mid-tone enough that
they may survive dark as-is — **measure, don't guess** (see contrast method below). If they need
dark counterparts, define both ends in one place shared by `schema-to-flow.ts` and the legend.

## Contrast methodology (used across this feature; reuse it)

WCAG AA: 4.5:1 for normal text, 3:1 for large text/graphics. Measure the **composited** color —
paint candidate colors into a canvas 1×N, stacking translucent layers over the real page
background, read pixels back, then compute relative luminance. Two traps hit during this feature:
Tailwind only generates classes that appear in source (probing a class that's never in source
silently resolves to transparent — always echo the resolved color in the probe output), and
`rtk`-filtered output garbles verification (use `/usr/bin/git` and plain tools when verifying).

## Verifying in the live app (after T054, or with a local `file:` link during development)

- The user's stack: old backend image on `:8000` (its `/api/config` lacks `dark_theme` — that's
  fine, the frontend dev-server fallback enables the theme when the flag is absent under
  `import.meta.env.DEV`), Vite dev server on `:8080` (`.claude/launch.json`, name `frontend-dev`).
- Dark is the default; the switch lives in the account menu (bottom-left ellipsis →
  "Light theme / Dark theme", alpha badge). It works logged-out.
- The visualizer page: `/schema` (renders `pages/schema/graph.tsx`).
- Pre-paint script reads `localStorage["infrahub.theme.resolved"]`; clear storage for a
  fresh-visitor run.

## Workflow order (from the root AGENTS.md — submodule discipline)

1. Branch + implement + PR **on the upstream repo** first. Run the package's own gates
   (`npm run lint`, its vitest browser tests, both builds).
2. Merge upstream (T053).
3. Only then, in infrahub: bump the submodule pointer, pass `theme={useResolvedTheme()}` at the
   embed site(s), and open that as a follow-up commit/PR on the stacked branch
   `dark-theme-completion-infp-46` (draft PR #10295, base `bab-dark-theme-app`).
4. T055 check: `git diff` on the infrahub side must contain no visualizer styling — only the
   pointer bump and the prop.

## Related context (only if needed)

- Spec: [spec.md](./spec.md) (US7, FR-016), plan: [plan.md](./plan.md) (R8 covers the visualizer).
- The stacked-PR series: #10284 (`bab-dark-theme-app`, base) ← #10295
  (`dark-theme-completion-infp-46`, this feature).
- Remaining sibling work, not this session's problem: Phase 3 user preference (GraphQL — Ask
  First gate), Phase 10 cross-cutting (contrast audit, changelog, docs, `/pre-ci`).
