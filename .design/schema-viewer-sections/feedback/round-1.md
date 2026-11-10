# Round 1 feedback

Source: a *Copy all notes* block pasted into the session by Paul on 2026-11-10. No PR comments
yet on https://github.com/opsmill/infrahub/pull/11519. Copied word for word below.

```md
<!-- design-jam:schema-viewer-sections -->
## design-jam feedback — schema-viewer-sections

### Current knobs (Grouped lists · rev 1)
- Show where each field comes from (`fieldSource`): false — Grouped lists only

### Grouped lists · rev 1 — 1 note, 1 open
http://localhost:8095/_proto/schema-viewer-sections?dj.variant=grouped&dj.rev=1&dj.k.fieldSource=0

1. **Containers** — if containers are still in this tab, it must be updated to be more understandable

this applies to all directions that still have the containers property
   `div > div > section > div:nth-of-type(2) > div:nth-of-type(2) > div > div:nth-of-type(3) > dl`

### Layout tab · rev 1 — 1 note, 1 open
http://localhost:8095/_proto/schema-viewer-sections?dj.variant=layout&dj.rev=1&dj.k.fieldSource=0

1. **Detailsbuilt in** — make the layouts consistent with the curernt ui of the schema viewer components, it looks different and the title is not very differnt from the content
   `div > div > section > div:nth-of-type(2) > div:nth-of-type(2) > div > div:nth-of-type(1) > div`
```

## Triage (with Paul, 2026-11-10)

Paul kept all three directions for another round rather than picking one.

1. **Containers block on Properties** (Grouped lists, applies to every direction with the
   block): addressed in rev 2 of Grouped lists, Layout tab and Section filter. The block is
   replaced by a "Sections" list with one row per section in detail page order: label, name,
   description, field count, source ("built in", "declared here", "from <generic>") and
   "starts collapsed". The label opens the section: the Attributes tab at that heading
   (Grouped lists), the Layout card (Layout tab), or the filter set to it (Section filter).
   Today stays unchanged as the baseline.
2. **Layout cards look different from the viewer, title too close to the content** (Layout
   tab): addressed in Layout tab rev 2. Each section is a field accordion (`AccordionStyled`):
   card surface, chevron, bold label, field count and source in muted text, description under
   it; rows sit on the panel surface like an open accordion's property rows.
3. **Field sources** (knob turned off in both notes): the knob now defaults to off. The knob
   default is panel-wide, so rev 1 links without `dj.k.fieldSource` also open with it off.

Not posted on the PR: the notes came from Paul's pasted block, not from PR comments.
