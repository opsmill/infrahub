# 02 — Directions

Prototype: **http://localhost:8080/_proto/branch-details** (dev server; log in as the local admin).

- `?variant=current | checkpoint | rail | tab`
- `?scenario=incident | running | unknown | all-clear | no-repos`
- `?repos=1–40`
- `?rows=<rows before "Show all">`
- `?rail=<px>`

Every control writes to the URL, so a pasted link opens on exactly the state you meant. Keys `1`–`4`
and `←` / `→` switch variants.

Code: `frontend/app/src/pages/_proto/branch-details/` (throwaway), one marked route block in
`src/app/router.tsx`. Built from `@infrahub/ui` (`Button`, `LinkButton`, `Card`, `Modal`,
`Popover`, `Checkbox`, `Menu`, `Spinner`) and `shared/` (`Badge`, `Accordion`, `DateDisplay`,
`Alert`). No new components. Data is mocked, per the user's choice in phase 1.

## Worst-case data in every variant

The **incident** scenario is the default:
- a 60-character repo name with a failed generator (`KeyError: 'asn'…`)
- a repo whose credentials are rejected, with a failed import from 3 days ago
- a read-only repo pinned to a tag
- a repo whose checks failed earlier and passed on the latest run, which must not warn
- 180 of 300 artifacts failed
- one generator run that isn't linked to any repo
- a 60-character branch name with a two-line description

The other scenarios:
- **Running:** a generator and 212 artifacts are still in progress.
- **Unknown:** the task query failed.
- **All clear:** every latest run passed.
- **No repos:** the branch isn't synced with Git.

The repo slider goes up to 40.

Each variant renders every scenario. The scenarios are what the table below is judged on.

---

## 1. Current (baseline)

Today's Details tab, unchanged.

- **Bets on:** nothing. It's here so every other direction is measured against something real.
- **Costs:** the incident reproduces exactly. Merge goes straight through with a failed generator and
  180 failed artifacts, because the page never mentions repositories.
- **Best for:** reminding reviewers what "do nothing" means.

## 2. Checkpoint: repos inline, Merge opens a confirmation dialog

The Details tab gains a **Repositories** card under the action row: a table with Repository,
Commit, Synced, Import, Generators and Checks, plus an Artifacts row. Rows with problems sort to the
top, and the list collapses after N rows.

Merge doesn't look any different until you press it. If anything failed, is running or is unknown,
a `Modal` lists each issue with its error line and a Logs link, with **Cancel** (focused) and
**Merge anyway**. If everything is clear, Merge goes straight through as it does today.

- **Bets on:** the moment of the click being the only moment that matters. It interrupts exactly
  once, exactly when the risk is real.
- **Costs:**
  - Until you click Merge, nothing near the button says it's risky. The evidence sits below the fold
    on a long branch.
  - A dialog is the easiest warning to learn to click through.
  - The table needs about 720px, so it scrolls sideways below that.
- **Best for:** teams that merge rarely and deliberately, where one interruption is acceptable and the
  table is a reference they read afterwards.
- **Precedent:** `modal-delete-branch.tsx` uses the same dialog shape.

## 3. Readiness rail: a sticky right rail owns the verdict and the Merge button

A two-column layout. The main column holds the attributes, a compact repo list (one line of
metadata, three labelled status icons) and the branch tasks.

The right rail is sticky and contains:
- the **verdict** ("Not ready: tasks failed" / "Not ready yet: tasks running" / "Readiness
  unknown" / "Ready to merge")
- the issue list, with error lines and Logs links
- the **Merge** button

When there's a problem, Merge becomes **Merge anyway** and stays disabled until you tick an inline
checkbox that names the consequence ("Artifacts on the default branch may be stale"). There's no
dialog. The secondary actions sit under the rail.

- **Bets on:** readiness being visible *before* anyone reaches for Merge, and the acknowledgement being
  a deliberate act rather than a reflex "OK".
- **Costs:**
  - The biggest structural change of the four. The action row moves out of the main column, and the
    page loses about 380px of width for content.
  - Below the `lg` breakpoint the rail stacks under the content, which puts Merge at the bottom.
  - The rail is always tinted, so on a healthy branch it's a green block that people learn to
    ignore.
- **Best for:** teams that merge from this page several times a day, where the verdict is the reason
  they opened it.
- **Control to tune:** `?rail=` sets the rail width. 380px fits the 60-character error line with
  truncation.

## 4. Repositories tab: evidence gets its own tab, Merge moves to the header

A new **Repositories** tab between Details and Data, with an issue count badge: red for failures,
blue for running, `?` for unknown. It holds a dense matrix (Repository, Commit, Synced, Remote,
Import, Generators, Checks) where each row expands to show the latest run per workflow: title,
error line, time, "N runs on this branch", and View logs. An Artifacts row closes the table.

Merge moves to the **page header** with a status dot. The other actions go into a `⋯` menu. When
there's a problem, pressing Merge opens a `Popover` anchored to the button, listing the first three
issues with **Review repositories** (focused, switches tab) and **Merge anyway**. The Details tab
gets a one-line status banner pointing to the tab.

- **Bets on:** repo state being a view of the branch in its own right, next to Data, Files and
  Artifacts, and on a warning that stays close to the button it's about.
- **Costs:**
  - The evidence is one tab away. Someone who stays on Details sees only the banner.
  - Moving Merge into the header and the other actions into a menu changes muscle memory for every
    branch action, not just this one.
  - A popover is lighter than a dialog, and easier to dismiss without reading.
- **Best for:** branches with many repositories, where the matrix is the fastest scan, and teams that
  already read the branch page tab by tab.

---

## What differs, on one line each

| | Where the evidence lives | When the warning appears | How you get past it |
|---|---|---|---|
| Current | nowhere | never | — |
| Checkpoint | Details tab, table under the actions | on Merge press | dialog, "Merge anyway" |
| Readiness rail | sticky right rail, always visible | before the press | inline checkbox, then "Merge anyway" |
| Repositories tab | its own tab + banner on Details | on Merge press | popover, "Merge anyway" |

## Found while building (true of every direction)

- **Nothing to check doesn't mean "passed".** With no repositories, the first build showed "All
  latest runs passed" in green. Fixed: all variants now say "Nothing runs on this branch" in
  neutral grey.
- **Workflow before repo name.** In the popover, a 60-character repo name pushed "Generators" out of
  view. Fixed by putting the workflow first. Anywhere space is tight, the workflow should lead.
- **Pre-existing:** `DateDisplay` wraps a `<span>` in `Tooltip nonInteractiveTrigger`, which logs a
  react-aria "`<Focusable>` child must have an interactive ARIA role" warning for every date on the
  page. It's in the production component, not the prototype.
- **The prototype has no permission checks**, matching today's buttons (logged in or not). Out of
  scope per the brief.
