# Design transcription — "Git sync visibility" canvas

This document is a transcription of the Claude Design canvas **"Git sync visibility"**
(`Git sync visibility.dc.html`), a four-section multi-artboard design filed under
**INFP-671 · Git repository sync visibility**.

- **Section 1 — "The repository page" is the area IFC-3130 works in.** It is transcribed
  exhaustively below (artboards 1a, 1b, 1c).
- **Sections 2, 3 and 4 belong to other tickets** (the Commits tab, the branch list,
  the branch detail view). They are summarised in one short paragraph each at the end,
  purely so a reader knows what is deliberately out of scope.

**This is a verbatim transcription of the canvas, including everything IFC-3130 does not
build.** Section 1 draws a `Last import` column, an `Upstream` column, `N behind` pills and
a row-action menu, all of which the ticket puts out of scope; it also uses labels
(`Import status`, `Git state`) that FR-005 forbids rendering, and one `Details` card where
the feature ships two. Nothing here is a statement of what ships. Read it against
**[plan.md](plan.md)**, whose *Design-to-spec reconciliation* table says column by column
what is built and whose *divergence register* lists every place this feature departs from
the canvas.

Labels, copy and hex values below are verbatim. No implementation is proposed here.

---

## Up front: one card or two?

**The design uses ONE card, titled `Details`, split internally into two labelled
groups.** It does not introduce a second card for branch-local Git values.

The Details card body is divided by two sub-headers (a full-width row, `background:#fafafa`,
`border-top:1px solid #e5e7eb`, `padding:7px 12px`, label in 11px/600 uppercase
`letter-spacing:0.07em` `color:#78716c`, followed by a 12px `color:#a3a3a3` caption):

| Group header | Caption beside it | Fields in this group |
| --- | --- | --- |
| `Repository` | `the same on every branch` | Name, Description, Location, Credential, Default branch, Operational status, Activity, Internal status, Tags |
| `On this branch` | the current branch name (e.g. `feat/add-site-fra1`, `main`) | Import status, Import error (error state only), Commit, Upstream commit — plus `Ref` on a read-only repository (1c) |

A **second, separate card titled `Branches`** is added *below* the Details card in the
same main column. On a read-only repository (1c) that card is replaced by a card titled
`Infrahub branches`. So: **Details (2 internal groups) + Branches = two cards total**, and
the repository-wide vs branch-local distinction lives *inside* the Details card, not
across two cards.

---

## Section 1 — The repository page (the area IFC-3130 works in, drawn in full)

### Section intro copy (verbatim)

> **INFP-671 · Git repository sync visibility**
> # 1 · The repository page
> Everything the repository page needs to say, added to the object detail view it already
> uses. The Details card gains three attributes and a divider between repository-wide and
> branch-local values; one Branches card is added below it; a Git status icon joins the top
> bar and turns red when the integration failed on the branch you are on. 1a is a branch
> whose import failed, 1b the same page with nothing wrong, 1c a read-only repository.

Artboard frame: 1440px wide. Heights: 1a = 1310px, 1b = 1230px, 1c = 1140px.

---

### Colour reference (every hex used semantically in section 1)

**Status chips — `Import status` / `Git state` values** (chip: `border-radius:6px`,
`padding:4px 8px` in the Details card, `padding:2px 8px` `font-size:12px` in tables,
`min-height:24px`):

| Chip label | Background | Text colour |
| --- | --- | --- |
| `In Sync` | `#60a5fa` | `#000` |
| `Import Error` | `#f87171` | `#000` |
| `Syncing` | `#a855f7` | `#fff` |

**Chips — `Activity` values:**

| Chip label | Background | Text colour |
| --- | --- | --- |
| `Importing` | `#a855f7` | `#fff` |
| `Idle` | `#e5e7eb` | `#374151` |

**Chips — other Details rows:**

| Chip label | Background | Text colour |
| --- | --- | --- |
| `Online` (Operational status) | `#86efac` | `#000` |
| `Active` (Internal status) | `#86efac` | `#000` |

**Row tints (the `background` of a definition-list row or of a table cell):**

| Meaning | Hex |
| --- | --- |
| Commit in Infrahub (teal) | `#e9f7fa` |
| Commit on the remote / upstream (purple) | `#f4eefa` |
| Activity row (new attribute highlight) | `#f0fbfd` |
| Branch-local failure rows (Import status + Import error in 1a) | `#fff5f5` |
| Failing cell in the Branches table (Import status cell, 1a row 1) | `#fef2f2` |
| Group-header rows inside the Details card | `#fafafa` |
| Neutral table body cell | `#f9fafb` |
| Table header cell / plain body cell | `#fff` |

**Semantic / chrome colours:**

| Use | Hex |
| --- | --- |
| Error body text (Import error copy) | `#7f1d1d` |
| Git status icon, error state: border | `#fecaca` |
| Git status icon, error state: background | `#fef2f2` |
| Git status icon, error state: glyph | `#b91c1c` |
| Git status icon, error state: dot | `#dc2626` (11×11px, `border-radius:999px`, `border:2px solid #fff`, offset `top:-2px; right:-2px`) |
| Git status icon, neutral state: glyph | `#57534e` (standard 32×32 button chrome, `border:1px solid #e5e5e5`) |
| "N commits behind" pill: background | `rgba(8,120,149,0.1)` |
| "N commits behind" pill: text | `#087895` |
| Link colour (global `a`) | `#087895`, dotted underline, solid on hover |
| Active tab underline + label | `#0987a8` (`border-bottom:2px solid`) |
| Inactive tab label | `#6b7280` |
| Tab count pill | background `#f3f4f6`, text `#111827` |
| Neutral pill (`default`, `tag`, `branch`, Tags value) | background `#f3f4f6`, text `#111827` |
| `Commit` column header icon | `#0b6581` |
| `Upstream` column header icon | `#78258a` |
| Column-header filter icon (active) | `#4338ca` |
| Table cell borders | `#e5e7eb` |
| Card border / chrome border | `#e5e5e5` |
| Muted metadata text | `#6b7280`, `#78716c`, `#4b5563`, `#a3a3a3` |
| Label (`dt`) text | `#6b7280` |
| Card header text | `#404040` |

---

### Page structure, top to bottom (identical across 1a, 1b, 1c unless noted)

**Left sidebar** (256px, not part of the ticket, shown for context): Infrahub logo +
collapse icon; `Search` field with `⌘ K` hint; group 1 — `IPAM`, `Objects`; divider;
group 2 — `Proposed Changes`, `Branches`, `Object Management`, `Actions`,
`Integrations` (active: `background:#eef2ff`, `color:#4338ca`, trailing `mdi:dots-vertical`),
`Activity`, `Admin`; footer — avatar `WV` (`#0B97BB`), `Wim Van Deun`, ellipsis.

**Top bar** (50px), left to right:
1. 32×32 icon button, `mdi:calendar-clock` (time travel).
2. 256px branch picker: `mdi:source-branch` + branch name + divider + `lucide:chevrons-up-down`.
   - 1a: `feat/add-site-fra1` · 1b: `main` · 1c: `main`
3. Breadcrumb: `/` `Git Repositories` `/` `infrastructure-templates`
   (1c: `/` `Read-Only Repositories` `/` `acme-golden-configs`).
4. 32×32 tasks button (`assets/tasks-status.svg`).
5. **NEW — Git status icon**, 32×32, `mdi:source-branch`:
   - **1a (failure on the current branch):** `border:1px solid #fecaca`, `background:#fef2f2`,
     glyph `#b91c1c`, plus an 11px `#dc2626` dot at the top-right with a 2px white ring.
   - **1b and 1c (healthy):** standard button chrome, glyph `#57534e`, no dot.

**Page header row** (inside the main panel, `padding:8px 8px 6px 12px`):
- `h1` 20px/700 — `infrastructure-templates` (1c: `acme-golden-configs`)
- `lucide:copy` icon (14px, `#78716c`)
- `mdi:information-outline` icon (16px, `#78716c`)
- pushed right: 32×32 refresh button (`lucide:refresh-cw`), then
  `Edit` (`lucide:pencil-line`), `Schema` (`mdi:code-json`), `Actions` (`lucide:chevron-down`).

**Tab bar** (44px tall tabs, `gap:16px`, `padding:0 16px`) — labels in order, with count pills:

| # | Tab label | Count pill | State |
| --- | --- | --- | --- |
| 1 | `Details` | — | active (`#0987a8` underline + label) |
| 2 | `Commits` | `40` | inactive — **new tab, belongs to section 2** |
| 3 | `Queries` | `3` | inactive |
| 4 | `Transformations` | `4` | inactive |
| 5 | `Checks` | `2` | inactive |
| 6 | `Generators` | `1` | inactive |
| 7 | `Tasks` | `128` | inactive |
| 8 | `Objects` | `10` | inactive |

(Identical in all three artboards.)

**Card grid** — `display:grid; grid-template-columns:2fr 1fr; gap:8px; align-items:start;
padding:8px; background:#fff`, scrolls vertically.

- **Main column (2fr), in order:** `Details` card, then the `Branches` card
  (1c: `Infrahub branches`).
- **Aside (1fr), in order:** `Groups` card, then `Activities` card.

Card chrome (all cards): `border-radius:16px`, `background:linear-gradient(to bottom,#fafaf9 0%,#ffffff 10%)`,
`border:1px solid #e5e5e5`, `box-shadow:0 1px 1px rgba(0,0,0,0.02)`, `overflow:hidden`.
Card header: `border-bottom:1px solid #e5e5e5`, `background:linear-gradient(to bottom,#f5f5f5,#fafafa)`,
`padding:8px 12px`, `font-weight:500`, `color:#404040`, `letter-spacing:-0.01em`.

Definition-list row layout (Details card): `display:grid; grid-template-columns:200px auto;
gap:16px; padding:8px 12px; border-top:1px solid #e5e7eb`. Each `dt` is 32px tall, 500 weight,
`#6b7280`, prefixed by a 16px field-schema icon.

---

## 1a — "The repository page, with the Git information added"

Sub-caption: *Viewed from `feat/add-site-fra1` — the branch whose import failed.*

### Card: `Details`

Header: title `Details`, right-aligned action `Extra` with a `lucide:eye` 14px icon
(12px text, `#292524`).

**Group header —** `Repository` · caption `the same on every branch`

| Icon | Label | Value | Treatment |
| --- | --- | --- | --- |
| `mdi:text` | `Name` | `infrastructure-templates` | plain text |
| `mdi:text` | `Description` | `Site build templates and schema` | plain text |
| `mdi:text` | `Location` | `https://github.com/acme-net/infrastructure-templates.git` | plain text |
| `mdi:key-variant` | `Credential` | `github-app-acme` | link + trailing `mdi:information-outline` (14px, `#9ca3af`) |
| `mdi:text` | `Default branch` | `main` | plain text |
| `mdi:format-list-bulleted-square` | `Operational status` | `Online` | chip `#86efac` / `#000` + `mdi:information-outline` |
| `mdi:format-list-bulleted-square` | `Activity` | `Importing` | **row tinted `#f0fbfd`**; chip `#a855f7` / `#fff`, then 12px `#6b7280` caption `3 of 12 branches · last fetched 4 minutes ago` |
| `mdi:format-list-bulleted-square` | `Internal status` | `Active` | chip `#86efac` / `#000` |
| `mdi:tag-multiple` | `Tags` | `site-build` | pill `#f3f4f6` / `#111827`, 12px/600 |

**Group header —** `On this branch` · caption `feat/add-site-fra1`

| Icon | Label | Value | Treatment |
| --- | --- | --- | --- |
| `mdi:format-list-bulleted-square` | `Import status` | `Import Error` | **row tinted `#fff5f5`**; chip `#f87171` / `#000` + `mdi:information-outline` |
| `mdi:text-box-outline` | `Import error` | see copy below | **row tinted `#fff5f5`**; 13px, `line-height:1.6`, `color:#7f1d1d`; label `dt` is top-aligned (`align-items:flex-start`, `padding-top:6px`) |
| `mdi:text` | `Commit` | `8f3c2a1d9b4e7c05a2f1e6d3b8074c5a19fe2b6d` | **row tinted `#e9f7fa`**; monospace full 40-char hash, then `lucide:copy` (13px, `#9ca3af`), then the behind-pill (below) |
| `mdi:text` | `Upstream commit` | `a19cd44f8b02e7135c9a6d40be71fc38a25d9014` | **row tinted `#f4eefa`**; monospace full hash + `lucide:copy` (13px, `#9ca3af`) |

**`Import error` copy (verbatim, with its inline formatting):**

> **Schema file not found.** `.infrahub.yml` declares `schemas/site_fra1.yml`, which does
> not exist at `a19cd44`. The commit was fetched successfully; only the import failed.
> Merging this branch is blocked until the import succeeds. `View task log` (a link in the canvas; no destination drawn)

(`Schema file not found.` is bold; `.infrahub.yml`, `schemas/site_fra1.yml` and `a19cd44`
are monospace `code`; `View task log` is a link.)

**The behind-pill on the `Commit` row:** an anchor (target: the Commits tab, `#2a`) reading
`3 commits behind`, preceded by a `mdi:arrow-down` 11px icon. Styling:
`border-radius:999px`, `background:rgba(8,120,149,0.1)`, `color:#087895`,
`padding:2px 9px`, `font-size:11px`, `font-weight:600`, `text-decoration:none`, `flex-shrink:0`.

### Card: `Branches`

Header: title `Branches` + count pill `12` (`border-radius:999px`, `background:#f3f4f6`,
`padding:2px 7px`, 12px/500, `#111827`).

Toolbar row below the header (`padding:8px 12px`): a 32px tall, 260px wide search field,
`border:1px solid #e5e5e5`, `background:#fff`, placeholder text `Search branches`
(`color:#a3a3a3`, 13px) with a `mdi:magnify` 15px icon.

**Grid:** `grid-template-columns: minmax(auto,230px) 150px 165px 125px 125px 40px`
(six columns; the last is the 40px row-menu column).

**Column headers** (40px tall, `font-weight:500`, `background:#fff` unless noted,
`border-top`/`border-bottom`/`border-right` `1px solid #e5e7eb`):

| # | Header text | Icon | Header cell tint | Notes |
| --- | --- | --- | --- | --- |
| 1 | `Branch` | — | `#fff` | row-identity column |
| 2 | `Import status` | `mdi:format-list-bulleted-square` (`#78716c`) | `#fff` | trailing `mdi:filter-variant` 16px, `margin-left:auto`, `color:#4338ca` (active filter) |
| 3 | `Commit` | `mdi:source-commit` (`#0b6581`) | **`#e9f7fa`** | |
| 4 | `Upstream` | `mdi:source-commit` (`#78258a`) | **`#f4eefa`** | |
| 5 | `Last import` | `mdi:calendar-clock` (`#78716c`) | `#fff` | |
| 6 | *(empty)* | — | `#fff` | 40px row-menu column |

**Rows** (each cell 40px tall, `padding:8px`; row-identity cell is `font-weight:500` and
carries a `mdi:source-branch` 14px `#78716c` icon before the link; commit cells are
`font-family:ui-monospace,monospace; font-size:13px`; `Last import` cells are 13px `#4b5563`;
the menu cell is a centred `mdi:dots-vertical` 15px `#78716c`):

| Branch (link) | Import status | Commit | Upstream | Last import |
| --- | --- | --- | --- | --- |
| `feat/add-site-fra1` | chip `Import Error` `#f87171`/`#000`, **cell tinted `#fef2f2`** | `8f3c2a1` (mono, cell `#e9f7fa`) + pill `3 behind` | `a19cd44` (mono, cell `#f4eefa`) | `4 min ago` |
| `main` + pill `default` | chip `In Sync` `#60a5fa`/`#000` | `8f3c2a1` (cell `#e9f7fa`) | `8f3c2a1` (cell `#f4eefa`) | `2 min ago` |
| `feat/bgp-policies` | chip `Syncing` `#a855f7`/`#fff` | `c04e7b2` (cell `#e9f7fa`) + pill `1 behind` | `7d81aa9` (cell `#f4eefa`) | `running` |
| `feat/dc-fabric-v2` | chip `In Sync` `#60a5fa`/`#000` | `5b2f918` (cell `#e9f7fa`) + pill `2 behind` | `e77c105` (cell `#f4eefa`) | `51 min ago` |
| `fix/vlan-ranges` | chip `In Sync` `#60a5fa`/`#000` | `31ab7c6` (cell `#e9f7fa`) | `31ab7c6` (cell `#f4eefa`) | `6 min ago` |

Details on the row affordances:

- **Row identity** is the `Branch` column; the branch name is a link.
- **Default branch marking:** `main` carries an inline pill reading `default`
  (`border-radius:999px`, `background:#f3f4f6`, `padding:1px 7px`, 11px/600, `#111827`,
  `flex-shrink:0`), placed after the link.
- **Failing row emphasis:** only the `Import status` *cell* of `feat/add-site-fra1`
  is tinted `#fef2f2`; the rest of that row keeps the standard cell tints.
- **Behind pills** inside the `Commit` cell: `border-radius:999px`,
  `background:rgba(8,120,149,0.1)`, `color:#087895`, `padding:1px 7px`, 11px/600,
  sans-serif (`font-family:InterVariable,Inter,sans-serif` — explicitly overriding the
  monospace cell), `white-space:nowrap`, with a `mdi:arrow-down` 10px icon. They carry
  both a `title` and an `aria-label`:
  - `3 behind` — `title="3 commits behind the upstream commit"`, `aria-label="3 commits behind"`
  - `1 behind` — `title="1 commit behind the upstream commit"`, `aria-label="1 commit behind"`
  - `2 behind` — `title="2 commits behind the upstream commit"`, `aria-label="2 commits behind"`
- **No copy button** appears in the table's commit cells (copy affordances exist only on
  the full hashes in the Details card).
- **Row menu:** a `mdi:dots-vertical` icon in the trailing 40px column of every row.

**Card footer / pagination** (`padding:8px 12px`, `border-top:1px solid #e5e7eb`,
12px, `#78716c`), sitting directly below the table inside the card:

> `Showing 5 of 12 · ` `Load more` (a link in the canvas; no destination drawn)

### Aside cards (1a)

- **`Groups`** — header `Groups`; body `padding:12px` containing a single `-` (`#6b7280`).
- **`Activities`** — header `Activities`; three entries, each a `mdi:timeline-text` 16px
  `#9ca3af` icon plus a two-line block (title, then `#6b7280` meta):
  1. `Repository updated` / `2 minutes ago · main`
  2. `Import failed` / `4 minutes ago · feat/add-site-fra1`
  3. `Repository created` / `3 days ago · main`

### Designer annotation panels beside 1a

Two side-by-side panels below the artboard (each `flex:1`, white, `border:1px solid #e5e5e5`,
`border-radius:12px`, `padding:14px 16px`).

**Panel 1 — `Unchanged`** (verbatim):

- Object header, tab row, and the two-column `2fr / 1fr` grid.
- The Details card, at full width, with every attribute row in schema order and the Extra toggle intact.
- Groups and Activities in the right rail, in the same order.
- Row layout: 200px label column, field-schema icon, metadata tooltip, Dropdown values as coloured chips using the schema's own hex.

**Panel 2 — `Added`** (verbatim):

- **The Details card is split into two labelled groups** — repository-wide values, then values scoped to the branch in the header. Activity, operational status and credentials are global; import status, the error and both commits are branch-local. Without the divider the two kinds sat in one undifferentiated list.
- **The Commit row says how far behind it is** — a link reading "3 commits behind" next to the hash, following the convention GitHub uses on a branch view. It answers "how stale is this?" without making the reader compare two hashes, and it opens the Commits tab filtered to the pending range.
- **Three new attributes** (tinted above), which need no front-end work: `activity` as a Dropdown, `import_error` as TextArea, `upstream_commit` as Text.
- **`sync_status` becomes Import status** and covers one phase only, so "In Sync" stops meaning both fetch and import. Reachability stays where it already lives, on `operational_status`; fetch freshness is a timestamp on the Activity row, not a status of its own.
- **One new card** — Branches — using the existing Card, CardHeader and table-cell styling, and **one new tab**, Commits (2a), using the standard object table.
- **Two fixed tints** carry the commit distinction everywhere it appears: teal for the commit in Infrahub (`#e9f7fa`) and purple for the commit on the remote (`#f4eefa`).
- **A Git status icon** in the top bar, next to the activity tracker: a branch glyph that turns red with a dot when anything in the Git integration failed on the branch you are on, and stays neutral otherwise (as in 1b).

---

## 1b — "The same page, nothing wrong"

Sub-caption: *Viewed from `main`. Same rows, no red, nothing extra to read.*

Top bar branch picker reads `main`; the Git status icon is in its **neutral** form.
Page header, tab bar and grid are identical to 1a.

### Card: `Details` (1b)

**Group header —** `Repository` · caption `the same on every branch`

| Icon | Label | Value | Treatment |
| --- | --- | --- | --- |
| `mdi:text` | `Name` | `infrastructure-templates` | plain text |
| `mdi:text` | `Description` | `Site build templates and schema` | plain text |
| `mdi:text` | `Location` | `https://github.com/acme-net/infrastructure-templates.git` | plain text |
| `mdi:key-variant` | `Credential` | `github-app-acme` | link + `mdi:information-outline` |
| `mdi:text` | `Default branch` | `main` | plain text |
| `mdi:format-list-bulleted-square` | `Operational status` | `Online` | chip `#86efac` / `#000` + `mdi:information-outline` |
| `mdi:format-list-bulleted-square` | `Activity` | `Idle` | **row tinted `#f0fbfd`**; chip `#e5e7eb` / `#374151`, then 12px `#6b7280` caption `12 branches synchronised · last fetched 38 seconds ago` |
| `mdi:format-list-bulleted-square` | `Internal status` | `Active` | chip `#86efac` / `#000` |
| `mdi:tag-multiple` | `Tags` | `site-build` | pill `#f3f4f6` / `#111827` |

**Group header —** `On this branch` · caption `main`

| Icon | Label | Value | Treatment |
| --- | --- | --- | --- |
| `mdi:format-list-bulleted-square` | `Import status` | `In Sync` | chip `#60a5fa` / `#000` + `mdi:information-outline`; **row is NOT tinted** |
| `mdi:text` | `Commit` | `8f3c2a1d9b4e7c05a2f1e6d3b8074c5a19fe2b6d` | **row tinted `#e9f7fa`**; monospace + `lucide:copy` (13px, `#9ca3af`); **no behind-pill** |
| `mdi:text` | `Upstream commit` | `8f3c2a1d9b4e7c05a2f1e6d3b8074c5a19fe2b6d` | **row tinted `#f4eefa`**; monospace + `lucide:copy` |

**The `Import error` row is absent entirely** — not rendered empty.

### Card: `Branches` (1b)

Header `Branches` + count pill `12`. Same `Search branches` toolbar.

**Grid:** `grid-template-columns: minmax(auto,260px) 150px 130px 130px 130px 40px`
(note: the widths differ from 1a — 260px identity column, 130px commit/upstream/last-import).

**Column headers** — identical text, icons and header tints to 1a:
`Branch` · `Import status` (with the `#4338ca` `mdi:filter-variant`) · `Commit` (header cell
`#e9f7fa`, icon `#0b6581`) · `Upstream` (header cell `#f4eefa`, icon `#78258a`) ·
`Last import` · *(empty 40px)*.

**Rows** (all healthy; commit cells `#e9f7fa`, upstream cells `#f4eefa`, no behind-pills,
no tinted cells):

| Branch (link) | Import status | Commit | Upstream | Last import |
| --- | --- | --- | --- | --- |
| `main` + pill `default` | `In Sync` `#60a5fa`/`#000` | `8f3c2a1` | `8f3c2a1` | `2 min ago` |
| `feat/add-site-fra1` | `In Sync` | `a19cd44` | `a19cd44` | `3 min ago` |
| `feat/bgp-policies` | `In Sync` | `7d81aa9` | `7d81aa9` | `5 min ago` |
| `feat/dc-fabric-v2` | `In Sync` | `e77c105` | `e77c105` | `5 min ago` |
| `fix/vlan-ranges` | `In Sync` | `31ab7c6` | `31ab7c6` | `6 min ago` |

Note the row order differs from 1a: the default branch `main` leads the list here.
Each row ends with the `mdi:dots-vertical` menu cell.

**Card footer:** `Showing 5 of 12 · ` `Load more` (a link in the canvas; no destination drawn)

### Aside cards (1b)

- **`Groups`** — `-`
- **`Activities`**:
  1. `Commit imported` / `2 minutes ago · main`
  2. `Repository updated` / `14 minutes ago · main`
  3. `Repository created` / `3 days ago · main`

### Designer annotation panel below 1b — `Notes on the healthy state` (verbatim)

- **Import error is absent, not empty.** The card is one row shorter than 1a and there is no blank field inviting the reader to wonder what belongs there.
- **Idle gets the quietest chip in the set.** It is the state the repository is in almost all the time, so colour stays reserved for Fetching, Importing and failure.
- **The Git status icon holds its slot** in neutral form, so its red state never shifts the layout and is genuinely noticeable when it appears.
- **The two commit tints still read when the hashes match** — teal above purple says the comparison was made, not merely that it came out equal.

---

## 1c — "A read-only repository"

Sub-caption: *Tracks a pinned ref per branch. Nothing is pushed back to Git.*

Breadcrumb: `/` `Read-Only Repositories` `/` `acme-golden-configs`.
Page title `acme-golden-configs`. Branch picker `main`. Git status icon **neutral**.
Tab bar identical (same labels and counts). Grid identical (`2fr / 1fr`).

### Card: `Details` (1c)

**Group header —** `Repository` · caption `the same on every branch`

| Icon | Label | Value | Treatment |
| --- | --- | --- | --- |
| `mdi:text` | `Name` | `acme-golden-configs` | plain text |
| `mdi:text` | `Description` | `Vendor golden configuration templates` | plain text |
| `mdi:text` | `Location` | `https://github.com/acme-net/golden-configs.git` | plain text |
| `mdi:key-variant` | `Credential` | `github-app-acme` | link + `mdi:information-outline` |
| `mdi:format-list-bulleted-square` | `Operational status` | `Online` | chip `#86efac` / `#000` + `mdi:information-outline` |
| `mdi:format-list-bulleted-square` | `Activity` | `Idle` | **row tinted `#f0fbfd`**; chip `#e5e7eb` / `#374151`, then 12px `#6b7280` caption `4 branches tracking a ref · last fetched 52 seconds ago` |
| `mdi:format-list-bulleted-square` | `Internal status` | `Active` | chip `#86efac` / `#000` |
| `mdi:tag-multiple` | `Tags` | `golden-config` | pill `#f3f4f6` / `#111827` |

**There is no `Default branch` row on a read-only repository.**

**Group header —** `On this branch` · caption `main`

| Icon | Label | Value | Treatment |
| --- | --- | --- | --- |
| `mdi:text` | `Ref` | `v2.4.1` | monospace value, then a pill `tag` (`border-radius:999px`, `background:#f3f4f6`, `padding:1px 8px`, 11px/600, `#111827`) carrying a `mdi:tag-outline` 12px icon, then `mdi:information-outline` (14px, `#9ca3af`) |
| `mdi:format-list-bulleted-square` | `Import status` | `In Sync` | chip `#60a5fa` / `#000` + `mdi:information-outline` |
| `mdi:text` | `Commit` | `c7d1904e5a8b3f620d94e1c8a70b3fd52e6a1b48` | **row tinted `#e9f7fa`**; monospace + `lucide:copy` (13px, `#9ca3af`) |
| `mdi:text` | `Upstream commit` | `c7d1904e5a8b3f620d94e1c8a70b3fd52e6a1b48` | **row tinted `#f4eefa`**; monospace + `lucide:copy` |

### Card: `Infrahub branches` (replaces `Branches` on a read-only repository)

Header: title `Infrahub branches`, count pill `4` (`border-radius:999px`, `background:#f3f4f6`,
`padding:2px 7px`, 12px, `#111827`), then — pushed right (`margin-left:auto`), 12px, `#78716c` —
the caption **`Each branch tracks one ref`**.

**There is no search toolbar on this card.**

**Grid:** `grid-template-columns: minmax(auto,240px) 150px 140px 120px 120px 40px`.

**Column headers** (40px, `font-weight:500`, borders as elsewhere):

| # | Header text | Icon | Header cell tint |
| --- | --- | --- | --- |
| 1 | `Infrahub branch` | — | `#fff` |
| 2 | `Ref tracked` | `mdi:source-branch` (`#78716c`) | `#fff` |
| 3 | `Git state` | `mdi:format-list-bulleted-square` (`#78716c`) | `#fff` |
| 4 | `Commit` | `mdi:source-commit` (`#0b6581`) | **`#e9f7fa`** |
| 5 | `Upstream` | `mdi:source-commit` (`#78258a`) | **`#f4eefa`** |
| 6 | *(empty)* | — | `#fff` |

Note the status column is titled **`Git state`** here, not `Import status`, and there is no
filter icon on it. There is also **no `Last import` column**.

**Rows** (40px cells, 13px text; identity cell has the `mdi:source-branch` 14px `#78716c`
icon then a link; `Ref tracked` values are monospace followed by a kind pill; `Commit` cells
have `background:#e9f7fa`, `Upstream` cells `background:#f4eefa`; every row ends with the
`mdi:dots-vertical` menu cell):

| Infrahub branch | Ref tracked | Git state | Commit | Upstream |
| --- | --- | --- | --- | --- |
| `main` + pill `default` | `v2.4.1` + pill `tag` | `In Sync` `#60a5fa`/`#000` | `c7d1904` | `c7d1904` |
| `feat/site-madrid` | `v2.4.1` + pill `tag` | `In Sync` | `c7d1904` | `c7d1904` |
| `feat/wan-refresh` | `v2.5.0-rc1` + pill `tag` | `In Sync` | `9a3b8e2` | `f0512dc` |
| `feat/vendor-eos` | `main` + pill `branch` | `In Sync` | `4e8ca07` | `4e8ca07` |

Kind pills (`tag`, `branch`, `default`) all use `border-radius:999px`, `background:#f3f4f6`,
`padding:1px 7px`, 11px/600, `#111827`, `flex-shrink:0`.
Note `feat/wan-refresh` shows `In Sync` while its Commit and Upstream differ — the moved-ref
case is carried by the differing hashes, not by a chip.

**Card footer** (`padding:8px 12px`, `border-top:1px solid #e5e7eb`, 12px, `#78716c`) —
no pagination here, an explanatory line instead:

> `Nothing is ever pushed back to Git from these branches.`

### Aside cards (1c)

- **`Groups`** — `-`
- **`Activities`**:
  1. `Commit imported` / `2 minutes ago · main`
  2. `Repository updated` / `14 minutes ago · main`
  3. `Repository created` / `3 days ago · main`

### Designer annotation panel below 1c — `Notes` (verbatim)

- A read-only repository **tracks one ref per Infrahub branch**, so the Branches card becomes an **Infrahub branches** card with a Ref tracked column. It does not mirror Git branches, and there is nothing to create on the Git side.
- The **Ref row sits in the branch group**, not the repository group: `ref` is branch-aware in the schema, so two Infrahub branches can legitimately pin different tags. `feat/wan-refresh` is on `v2.5.0-rc1` while everything else is on `v2.4.1`.
- **No extra status value is introduced.** Git state stays within the four the schema already defines, and the fact that a pinned ref has moved is carried by the two commit columns differing plus the notice below the table — not by a fifth chip.
- The **same two commit tints** apply unchanged, and **Default branch is gone** — the read-only schema has no such attribute.
- The footer line states the one-way nature explicitly. Worth deciding with the team whether that belongs on the page permanently or only in the docs.

---

## States NOT shown in section 1

The canvas's section-1 artboards show only three states of the repository page:
the error state (1a), the healthy state (1b) and the read-only variant (1c).
**No loading, empty, error-fetching, not-yet-available or preview-notice states are drawn**
for the Branches card or the Details card. The only inline help copy present is:

- the two group captions — `the same on every branch` and the branch name;
- the `Import error` body copy (1a);
- the `Each branch tracks one ref` header caption (1c);
- the footer line `Nothing is ever pushed back to Git from these branches.` (1c);
- the pagination footer `Showing 5 of 12 · Load more` (1a, 1b);
- the search placeholder `Search branches` (1a, 1b).

---

# Out of scope — sections 2, 3 and 4 (other tickets)

## 2 · The Commits tab

Two 1440px artboards, **2a "The Commits tab"** (standard repository, viewed from
`feat/dc-fabric-v2`) and **2b "The Commits tab on a read-only repository"**. The commit
history moves off the Details card into its own tab using the standard object table, with a
`Search commits` field and a branch selector in the toolbar. Table grid
`290px 1fr 150px 150px 40px`; column headers: `Commit`, `Message`, `Author`, `Date`, and a
40px row-menu column. Rows carry badges on the hash — a teal band for what Infrahub is
running and a purple band with an `On remote` badge (`background:#c996c0`, text `#3d1d38`,
`mdi:cloud-outline` icon) for the remote head; on 2b that badge becomes `Ref head`. The
annotation panels discuss why there is no per-commit status column, that commits are read
live from Git (limiting sort/filter), that the tab follows the header branch, that the row
menu holds only commit-scoped actions, and — on 2b — that `Import this commit` is the action
worth adding, with an open question about whether it should rewrite `ref` to the hash.

## 3 · The branch list

One artboard, **3a "Three columns added to the branches table"** (twelve branches, one
repository failing). The existing branches table gains three columns —
repository, Git state and the imported commit. Card header `Branches` with count pill `12`
and a `Search branches` field; grid
`minmax(auto,280px) 150px 200px 140px 175px 180px 150px 40px` with `min-width:1100px`.
Column headers in order: `Name`, `Status`, `Repository`, `Git state`, `Commit`,
`Proposed changes`, `Branched from`, plus a 40px row-menu column. An annotation panel titled
**"Open questions this raises"** asks how the three new columns behave when a branch is
linked to more than one repository, notes that branches not synchronised with Git need a
distinct empty state (`Not synced with Git`, not a dash), and warns that `Status` (branch
lifecycle) and `Git state` (import outcome) now sit next to each other as similar-looking
pills.

## 4 · The branch detail view

Five 1440px artboards: **4a "Synchronised, everything in sync"**, **4b "Branch import
failed"**, **4c "Two repositories failed to import"**, **4d "No Git counterpart"**, and
**4e "A branch with both repository kinds"**. The branch page's existing attributes card is
untouched; one new card titled **`Git repositories`** (with a count pill) is added below it,
listing every repository the branch is synchronised with. Its columns are `Repository`,
`Git state`, `Commit`, `Upstream`, `Last import` — and on 4e, where standard and read-only
repositories mix, `Repository`, `Kind`, `Tracking`, `Git state`, `Commit`, `Upstream`. 4d
replaces the table with an empty state headed **`Not synchronised with Git`** reading "This
branch exists only in Infrahub. It has no Git counterpart, so there is no commit to import
and nothing to compare against a remote." Errors appear as bands inside the card, below the
table, each naming its repository and linking to its own task log. The annotation panels
cover the unchanged attributes card, the reuse of the teal/purple commit tints, per-repository
(not per-branch) Git state, the red Git status icon agreeing with the repository page,
stacked-band scalability at four or five simultaneous failures, that a moved ref is not a
status (amber notice, not an error, with a `Re-import` action), and an open question about
whether Merge should be disabled when an import has failed.
