# Mermaid support in the markdown renderer

**Date:** 2026-06-15
**Status:** Approved (design)
**Area:** `frontend/app` — markdown rendering

## Goal

Render Mermaid diagrams from ` ```mermaid ` fenced code blocks in markdown
**artifacts** (documentation generated in Infrahub, displayed via the data
viewer). Because every markdown surface in the app renders through the shared
`MarkdownRender` component, enabling mermaid there also — intentionally —
enables diagrams in proposed-change comments, proposed-change descriptions, and
the markdown editor's live preview.

The artifact/documentation use case is the driver. The other surfaces come
along for free through the shared component, and that is accepted.

## Background

Current markdown rendering (verified in codebase):

- Library: `react-markdown` v10.1.0
- Remark plugins: `remark-gfm` v4.0.1, `remark-breaks` v4.0.0
- No rehype plugins today; no syntax highlighting on markdown code blocks
- Core component `MarkdownRender` is a thin (~6-line) wrapper around the
  synchronous `Markdown` component from `react-markdown`
- Components live in `frontend/app/src/shared/components/editor/markdown/`:
  - `markdown-render.tsx` — read-only renderer (the shared core)
  - `index.tsx` (`MarkdownEditor`) — CodeMirror editor + live preview
  - `markdown-viewer.tsx` (`MarkdownViewer`) — rendered/raw toggle
- Markdown styling: `frontend/app/src/app/styles/markdown.css`
- Consumers: PC comments, PC descriptions, form textareas, data viewer
  (`text/markdown` artifacts)
- The app is **light-theme only**.
- No mermaid usage anywhere in the repo today.

## Approach

### Key mechanism: async react-markdown + client-side rehype-mermaid

`rehype-mermaid` is an **asynchronous** rehype plugin. react-markdown's
synchronous `Markdown` component cannot run async plugins, so the canonical
integration uses **`MarkdownHooks`** (the client-side async component, available
in react-markdown v10) — see the rehype-mermaid README.

Critically, `rehype-mermaid` renders through **`mermaid-isomorphic`**, which
ships a `browser` export (`dist/browser.js`) that renders diagrams with
real-DOM mermaid. Vite resolves the `browser` export condition automatically,
so the default **`inline-svg`** strategy renders the SVG **client-side, in the
browser, without Playwright**. Playwright is an *optional* peer dependency used
only in Node/SSR environments and is never installed or bundled here.

This means rehype-mermaid does the diagram rendering itself; the app does not
need a custom mermaid lifecycle.

### Rejected alternatives

- **Synchronous `Markdown` + `pre-mermaid` strategy + a hand-written
  `useMermaid` hook** (calling `mermaid.run()` in an effect, scoping to a
  container ref, resetting `data-processed`, and a `key`-based remount). This
  works, but reimplements — manually and more error-prone — what
  `MarkdownHooks` + `inline-svg` do natively. Rejected once the async-component
  path was confirmed viable client-side.
- **rehype-mermaid `img-svg` / `img-png` strategies** — produce data-URI images
  and, in Node, require Playwright. No benefit over `inline-svg` here.
- **Third-party React wrappers** (`react-mermaid2`, etc.) — mostly unmaintained.

### Bundle strategy: fence-detection lazy split

`rehype-mermaid` transitively pulls in `mermaid` + `katex` +
`@fortawesome/fontawesome-free` (via `mermaid-isomorphic`) — heavier than
mermaid alone. `MarkdownHooks` also gates the **entire** markdown block on the
async pipeline (the whole comment/artifact shows the fallback until mermaid
finishes, not just the diagram). Both costs must be kept off the common,
diagram-free path (most comments and descriptions).

Therefore `MarkdownRender` branches on whether the text contains a mermaid
fence:

- **No mermaid fence** (`/```\s*mermaid/` does not match) → render with the
  current synchronous `Markdown` component and existing plugins. Behavior and
  bundle are unchanged; the mermaid/katex/fontawesome code is never loaded.
- **Mermaid fence present** → render a `React.lazy`-loaded `MarkdownWithMermaid`
  subcomponent. `React.lazy` + a dynamic `import()` ensures rehype-mermaid (and
  its transitive deps) are fetched only when a diagram is actually present.

## Components

### `MarkdownRender` (modified)

`frontend/app/src/shared/components/editor/markdown/markdown-render.tsx`

- Detects a mermaid fence in `markdownText`.
- No fence → renders the existing synchronous `Markdown` (unchanged path).
- Fence present → renders `<Suspense fallback={…}><MarkdownWithMermaid …/></Suspense>`
  where `MarkdownWithMermaid` is `React.lazy(() => import('./markdown-with-mermaid'))`.
- The `Suspense` fallback is a plain synchronous `Markdown` render of the same
  text, so content (including the raw mermaid block) is visible while the chunk
  loads.

### `MarkdownWithMermaid` (new, lazy-loaded)

`frontend/app/src/shared/components/editor/markdown/markdown-with-mermaid.tsx`

- Uses `MarkdownHooks` with:
  - `remarkPlugins={[remarkGfm, remarkBreaks]}` (same as base)
  - `rehypePlugins={[[rehypeMermaid, options]]}`
- rehype-mermaid options:
  - `strategy: 'inline-svg'` (default; explicit for clarity)
  - `mermaidConfig: { securityLevel: 'strict', theme: 'default' }`
  - `errorFallback`: returns a node containing the raw diagram source (see
    Error handling)
- `MarkdownHooks` `fallback` prop: a plain synchronous `Markdown` render of the
  same text, so the document text appears immediately and the diagram swaps in
  when the async pipeline resolves.

## Re-rendering

Handled natively by `MarkdownHooks`: when `markdownText` changes (e.g. editor
live preview), react-markdown re-runs the pipeline and re-renders. No manual
`key` remount, `mermaid.run()` effect, or `data-processed` management — the
rendering is owned by the react-markdown pipeline, not hand-written DOM
mutation.

## Security

`securityLevel: 'strict'` passed via rehype-mermaid's `mermaidConfig`. Rationale:
comments are untrusted user input rendered to other users, and mermaid has a
history of XSS via diagram labels and `click`/`call` directives. Strict escapes
HTML in labels and disables click/script interactions.

Not chosen: `'loose'` (no feature here justifies the risk), `'sandbox'` (iframe
sizing pain for no benefit over strict here).

react-markdown does not pass raw HTML through by default (no `rehype-raw`).
rehype-mermaid inserts the rendered SVG as proper hast element nodes (not raw
HTML strings), so it renders without `rehype-raw`; with `securityLevel: 'strict'`
the SVG content is safe.

## Error handling

`rehype-mermaid`'s `errorFallback(element, diagram, error, file)` option returns
a fallback node when a diagram fails to render. The implementation returns a
node showing the **raw diagram source** (the user's typed mermaid), not
mermaid's red "Syntax error" graphic — for an authoring/documentation use case,
showing the source helps the author fix it. If `errorFallback` returned nothing,
rehype-mermaid would remove the code block, which we explicitly avoid.

## Lazy loading & loading state

- Fence detection + `React.lazy` + dynamic `import()` keep rehype-mermaid and
  its transitive deps (mermaid, katex, fontawesome) out of the bundle on the
  common diagram-free path.
- Two transient states, both falling back to a plain synchronous `Markdown`
  render of the same text so content is never blank:
  1. `Suspense` fallback while the lazy chunk loads.
  2. `MarkdownHooks` `fallback` while the async mermaid pipeline resolves.
- **No dedicated spinner for v1** — the sync render is shown during both
  transients, which is strictly better than a spinner (text is readable
  immediately; only the diagram appears late).

## Styling

`frontend/app/src/app/styles/markdown.css`:

- `.markdown .mermaid svg`, or the SVG node rehype-mermaid emits,
  `{ max-width: 100%; height: auto }` — diagrams scale down to fit the container.
- Wrap diagrams in an `overflow-x: auto` container so genuinely oversized
  diagrams get a horizontal scrollbar instead of clipping or breaking layout.
- Pan/zoom deferred (not v1). Exact selector to be confirmed against
  rehype-mermaid's emitted markup during implementation.

## Theming

App is light-only, so `theme: 'default'` is fixed in `mermaidConfig`. No
dark-mode switching logic.

## Dependencies

Added to `frontend/app/package.json`:

- `rehype-mermaid` — the rehype plugin. Transitively brings `mermaid-isomorphic`
  → `mermaid`, `katex`, `@fortawesome/fontawesome-free`. All lazy-loaded behind
  the fence-detection split.

Not added:

- `mermaid` directly — it comes transitively; the app does not import it itself.
- `playwright` — optional peer dep, only for Node/SSR; Vite resolves
  `mermaid-isomorphic`'s `browser` export, so Playwright is neither installed
  nor bundled. Confirm at build time that the production bundle does not attempt
  to pull the Playwright-based Node renderer.

Compatibility with the installed `react-markdown` v10.1.0 / unified ecosystem to
be confirmed at install time; flag any peer-dep mismatch.

## Testing

**None** for this feature, per explicit user decision. (Noted that AGENTS.md
normally expects tests for new functionality, and that mermaid is hostile to
jsdom unit testing — real SVG layout is unimplemented there.)

## Changelog

Add `changelog/+mermaid-markdown-artifacts.added.md` (Towncrier orphan
fragment, category **Added**):

> Markdown artifacts now render Mermaid diagrams from ` ```mermaid ` code blocks.

## Explicitly deferred (not in v1)

- Custom mermaid theme matched to the app's design tokens.
- Pan/zoom interactivity for large diagrams.
- A dedicated loading spinner (the sync-render fallback covers the transients).
- Dark-mode theme switching (app is light-only).
