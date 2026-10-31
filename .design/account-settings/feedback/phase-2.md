# Feedback — phase 2 (directions, rev 1)

Gathered: pasted *Copy all notes* block from the owner, 2026-10-01 (no PR yet).

## Raw

> **Side nav · rev 1**, knobs: p2=on, prefs=own section, tokens=many, password=local,
> admin=on, longName=off
> `?dj.variant=side-nav&dj.rev=1&section=profile`
>
> 1. **Profile section header + details** (`div > div > div > div > div`): "Ensure paddings
>    and margins are consistent across pages"

## Triage

1. **addressed, next revision.** Cause confirmed in code: the reused section bodies bring
   their own outer padding, and the shell adds its own on top.
   - `DetailsLayout` (Profile) adds `p-2`, so the details card sits 8px inside the section
     header's left edge.
   - `GlobalPreferencesEditor` wraps itself in `<main className="p-2">`.
   - Tokens, Password and Preferences add none.

   The left edge and the top gap therefore change from section to section, in every
   direction, not only Side nav. Fix: the shell owns the gutter and section bodies render
   flush. That means stripping `DetailsLayout`'s padding through its `className`. For
   `GlobalPreferencesEditor`, which hard-codes `p-2`, the change is recorded as an
   implementation seam: it needs a `className` or no outer padding.

**Outcome:** the owner confirmed the note is about section *content*, not a pick of Side
nav, so it shipped as **rev 2 of all four directions** (`sections-v2.tsx`, frozen copies
`*/rev-02.tsx`). Measured in Side nav rev 2: every section's header and first card share
one left edge, with a 16px header-to-content gap. Tokens is 46px because the summary-badge
row sits between them, by design. P2-off branches keep today's padding on purpose: they
are the baseline being compared.
