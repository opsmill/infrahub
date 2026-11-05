# Decisions: instance badge and bar

Chosen direction: the tinted pill of `header-left` placed at the position of `header-right`, on the
right of the header before the task status and repository sync status. The delegate first picked
`header-left` unattended (reasons below); on 2026-11-05 the tech owner overturned the position: the
badge belongs with the other instance-level status indicators on the right. The tinted style stays.

- **Header-left over header-right**: the left edge of the content column is where the eye lands
  first; the solid badge on the right competes with "Add child prefix" and every primary action,
  and needs seven custom contrast pairs in dark mode. The tinted pill reuses the existing Badge
  variants, which already pass contrast in both themes.
- **Header-left over banner-strip**: the strip spends 16 to 28 px on every page and above the
  sidebar, and departs from the spec, which asks for a badge inside the header. Its label is small
  uppercase text far from where users work.
- **Header-left over sidebar-brand**: the sidebar header is 32 px high and collapses to a dot,
  which is the weakest form of the indicator; the login page has no sidebar, so the placement
  would not carry over.
- **Bar height 3 px** (`h-0.75`): visible at a glance above the rounded cards without reading as
  a border. 1 to 2 px disappears against the card edge; 4 px and above starts to look like a strip.
- **Badge max width `max-w-48`** (192 px) with `truncate` and a tooltip holding the full label: at
  `text-xs font-semibold` this shows about 24 characters, so most labels fit and a 32-character
  label truncates with the tail in the tooltip.
- **Tinted badge, not solid**: the existing `Badge` variants (`red`, `warning`, `green`, `blue`,
  `purple`, `gray`) are reused; `indigo` is the one new variant, on `--active` /
  `--active-surface`. No inline styles, no arbitrary values.
- **Gray when a label has no color**: the `gray` variant, so the badge is present but neutral.
- **Nothing rendered when nothing is set**: no reserved height for the bar, no empty badge, so
  instances without the setting look exactly as before.
- **Login page**: the bar at the top of the viewport, the badge centered above the logo in the
  login column (`gap-6` keeps it apart from the logo). The badge there uses the same component.
- **Settings form**: a second card "Instance identity" on the Global preferences page with a
  text `Input` (max length 32, helper text with the count) and a `Combobox` of the seven presets,
  each item prefixed with a `size-3 rounded-full` swatch in the preset's bar class, placeholder
  "No color". The existing `Combobox` is kept so the e2e helper `select_combobox_option` works.
- **Tooltip on every badge**, not only when truncated: measuring truncation needs a resize
  observer for a marginal gain; the full label in a tooltip is harmless when it is not truncated.

Knobs resolved: `barHeight = 3`, `badgeMaxWidth = 192` (`max-w-48`), `stripHeight` unused.
