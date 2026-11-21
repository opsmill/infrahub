# Round 1 feedback: the three directions at rev 1

Source: a *Copy all notes* block pasted by the owner in the design-jam session on
2026-11-16. The block carries no reviewer name. The notes are copied word for word.

<!-- design-jam:schema-migrations -->
## design-jam feedback — schema-migrations

### Current knobs (On the branch · rev 1)
- Screen (`view`): Staged schema change
- Impact calculation (`impact`): done

### On the branch · rev 1 — 3 notes, 3 open
http://localhost:8097/_proto/schema-migrations?dj.variant=branch-tab&dj.rev=1&dj.k.view=Staged+schema+change&dj.k.impact=done

1. **Schema changes6** — it can be confusing to have schema + schema changes
   `div > div > nav > div > span:nth-of-type(6)`
2. **Schema revision of feature/dc2-paris-edge-routers-device-rol** — it is very difficult to read everything
   `div:nth-of-type(1) > div > div > div > div:nth-of-type(1)`
3. **Impact calculated 17 minutes ago. Infrahub does not recalcul** — backgrounds are not great to diffentiate sections
   `div:nth-of-type(1) > div > div > div > section > div:nth-of-type(2)`

### In the review · rev 1 — 1 note, 1 open
http://localhost:8097/_proto/schema-migrations?dj.variant=review&dj.rev=1&dj.k.view=Staged+schema+change&dj.k.impact=done

1. **00030** — should it be in the details tab, in a new tab or like that to make it more clear?
   `div > div > div > header > div > div > button > span:nth-of-type(1)`

### On the schema page · rev 1 — 1 note, 1 open
http://localhost:8097/_proto/schema-migrations?dj.variant=schema-page&dj.rev=1&dj.k.view=Staged+schema+change&dj.k.impact=done

1. **Schema214** — it is very difficult to read all those details
   `div > header > div:nth-of-type(1) > div`

## Triage, 2026-11-16, agreed with the owner

The owner picked the combined direction (schema page, merge plan in the proposed change,
revision in the branch Details tab). The notes were removed from the prototype after this
triage, once per browser.

1. On the branch, note 1 ("schema + schema changes"): **addressed** in combined rev 1. No new
   branch tab; the revision and the staged schema change are rows in the Details tab.
2. On the branch, note 2 (revision line hard to read): **addressed** in combined rev 1. A
   revision block with the number first and the name and time beside it; the branch name
   is not repeated.
3. On the branch, note 3 (backgrounds): **addressed** in combined rev 1. White sections on
   the grey panel.
4. In the review, note 1 (where 00030 goes): **addressed** in combined rev 1. A row in the
   Details tab; the header button is removed.
5. On the schema page, note 1 (too many details): **addressed** in combined rev 1. The header
   has two lines, and the "Branch selected in the header" line is removed.
