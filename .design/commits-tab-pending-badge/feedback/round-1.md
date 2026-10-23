# Round 1 feedback (phase 2 directions)

Source: pasted by Paul Leménager in the session on 2026-10-23 (Copy all notes block).

<!-- design-jam:commits-tab-pending-badge -->
## design-jam feedback — commits-tab-pending-badge

### Current knobs (Pill · rev 1)
- Scenario (`scenario`): all

### Pill · rev 1 — 1 note, 1 open
http://localhost:8081/_proto/commits-tab-pending-badge/commits?dj.variant=pill&dj.rev=1&dj.k.scenario=all

1. **1,284** — what if there is commits that both are pending and need to be imported
   `div > div > div > nav > div > a:nth-of-type(9) > span > span`

## Triage

1. Declined (no change), decided by Paul Leménager on 2026-10-23; reason in `03-decisions.md`:
   - The backend gives one answer per repository and branch (`_resolve_remote_branch` in #11169): staging → pending import; branch that does not sync with Git → not on this branch; otherwise the branch's own remote branch → pending import. So a badge never has to show both kinds at once.
   - One overlap exists inside "not on this branch": when the default branch in Infrahub has not imported the newest Git commits yet, a rebase brings only the default branch's commit, not the newest ones. The API cannot tell these apart today.

Follow-up question from the user: "pending" and "need to be imported" are the same thing ("pending import"). There are two kinds only: pending import (an import brings them) and not on this branch (only a rebase brings them).
