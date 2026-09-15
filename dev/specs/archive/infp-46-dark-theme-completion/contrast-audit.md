# Contrast audit (T056, FR-021 / SC-009)

Run 2026-08-18 against a live development stack, both themes, WCAG 2.1 AA thresholds
(4.5:1 for normal text, 3:1 for large text — ≥24px, or ≥18.66px bold).

## Method

A Playwright sweep drives 12 routes twice (theme pinned through the storage keys the app itself
uses), injecting an auditor that walks every visible text node and measures the colour it renders
in against the surface it actually sits on. Colours are normalised and composited through a canvas
pixel, so `oklch()` values and translucent layers measure as the browser paints them — a naive
channel parse mis-reads `oklch()` as RGB bytes and produces garbage ratios, which is worth knowing
before trusting any similar tool.

Routes: `/`, `/login`, `/objects/NetworkDevice`, `/objects/NetworkDeviceType`, `/proposed-changes`,
a proposed-change detail (with a rendered Mermaid diagram), `/branches`, `/tasks`, `/ipam`,
`/graphql`, `/profile`, `/schema`.

## Result

**Zero AA failures in either theme** after the fixes below. The audit is what surfaced most of
them — every one was invisible to review by eye:

| Finding | Before | After | Fixed in |
|---|---|---|---|
| Sidebar active item, `text-indigo-500` both themes | 3.7 light / 4.3 dark | 6.3 / 6.2 (`--active` token) | `4739b1a5c` |
| Avatar ramp letters, `-600` text on `-50` tiles | 2.8–4.2 on four of seven hues (light) | 4.7–7.2 light, 9.0–12.5 dark | `e217f3304` |
| Alert close-button focus halo in dark | fixed `ring-offset-gray-50` | tokenised ring + offset | `c5cb03e34` |
| GraphiQL logo text on its light chrome | 4.26 (vendor alpha-muted neutral) | ≥4.5 (full-strength neutral, both themes) | this audit |

## Scope boundaries and limitations

- **Semantic palettes are out of scope** (status/severity badge colors, syntax highlighting, diff
  colors), per the task's boundary — they are tracked as a separate effort. Elements carrying
  data-driven inline colors (schema-defined role colors, kind palettes) are skipped for the same
  reason.
- **Gradient surfaces are skipped**, not measured: the auditor cannot know which stop sits behind a
  given glyph. The theme's gradients (`--card`, `--panel`, `--secondary`) are near-solid ramps of
  the surfaces that *were* measured, so the residual risk is low, but it is a real hole — text
  placed directly on a future high-range gradient would go unmeasured.
- **SVG internals are excluded**: Mermaid themes its own output, and its labels sit on shape fills
  rather than CSS backgrounds. The Mermaid test suite asserts its palette separately.
- Popovers, menus and modals are audited only where a route renders them by default; the earlier
  interaction sweep covered the common overlays by hand.
