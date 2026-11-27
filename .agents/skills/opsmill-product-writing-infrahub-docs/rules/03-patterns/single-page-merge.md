# Single-page merge

Used when a feature has one concept + one workflow and content fits under ~300 lines combined.

**Precedent:** Computed Attributes — PR #9120.

## File structure

- Create `docs/docs/<feature>/overview.mdx` — combine topic content (top) and guide content (rewritten below as how-to sections)
- Sidebar entry: `{ type: 'doc', id: '<feature>/overview', label: '<Feature>' }` — the merged page is the sidebar entry; no folder/category needed

## Body conventions

- Drop "Step 1/2/3" wording from headers; use action-named section headers ("Configure your X", "Verify your X")
- Numbered procedural lists *inside* sections stay numbered when sequence matters
- Replace running examples with placeholders like `<group-name>`, `<object-id>`

## Why a folder and overview.mdx for single-page merges too

Even when there is only one page, putting it at `<feature>/overview.mdx` keeps the URL stable regardless of later restructuring. If the page grows into a hub with child pages, nothing has to move — you only add siblings. Computed Attributes was done this way, and it matches every other hub in the docs.
