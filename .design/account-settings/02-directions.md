# 02 — Directions: account settings

Prototype: `/_proto/account-settings` (inside the app layout, real sidebar and header).
Every direction is `dj.rev=1`. Switch with the panel, or `?dj.variant=<id>`.

**Shared by all four:**
- **Knobs:** P2 on/off; Preferences as its own section or inside Profile; tokens data
  (many / empty / error / loading); password local or external; global-preferences
  permission on/off; long name with no description.
- **Deep links:** `?section=<id>` stands in for a real nested route per section (FR-003).
- **Sections:** identical in every direction (`sections-v1.tsx`), so the comparison is about
  structure only.
- **Theme picker:** Preferences now has one; today it exists only in the account menu.

`emil-prototype` normally loads a set of craft skills before building. They were not
loaded, because design-jam allows no extra skills in phase 2. Polish and surfaces come in
phase 4.

---

## Side nav — `dj.variant=side-nav`

**Bets on:** a settings shell. A grouped vertical nav on the left (identity on top,
*Personal*, then *Administration*), one section on the right.

**Costs:**
- It's the first vertical settings nav in the app (01-system.md § Missing). Implementing it
  means a new layout pattern, and possibly a shared primitive.
- 240px of width goes to the nav. That squeezes Profile's details-plus-aside layout at
  1280px.

**Best for:** growth. Sessions, SSO or notifications slot in as one more row. SC-001 and
SC-002 hold by construction: every section is named and one click away, at any size the
list will reach.

## Tabs — `dj.variant=tabs`

**Bets on:** keeping today's model. Identity header and horizontal tabs as now, but the
right tabs exist (Preferences, Global preferences pushed to the right) and each tab's
content does its job.

**Costs:**
- Five tabs is about the limit at 1280px. Sessions/SSO would overflow into a scroll or a
  "More" menu.
- Global preferences, an admin and instance-wide setting, sits in the same row as personal
  ones, separated only by position.

**Best for:** the smallest change. It reuses `LinkTab` as is, needs no new layout, and
nobody has to relearn anything. If the problem is mostly *content* (P2), not *structure*
(P1), this wins.

## Single page — `dj.variant=single-page`

**Bets on:** settings being few and short. Every section is stacked on one scroll with an
"On this page" rail that tracks position and jumps. Browser Ctrl+F finds any setting.

**Costs:**
- Profile (details, groups, activity) is long and pushes everything else down.
- Every section's queries load at once.
- Two forms (preferences, password) on one page raises the "which Save did I press"
  question.
- The rail is hidden below `lg`.

**Best for:** scanning: "what's my setup?" in one scroll. It's also the only direction
where SC-004 ("find the theme") works by Ctrl+F alone.

## Overview — `dj.variant=overview`

**Bets on:** a landing page that summarises state before you choose:
- "14 tokens · 3 expired · 3 never expire"
- "Theme: System"
- "Managed by your identity provider"

A card opens its section, and the section has a back link.

**Costs:**
- Every visit is two clicks to reach a setting (landing → section), which breaks SC-002's
  "one click from any other section" between sections.
- The summaries need data for every section on the landing page.
- The cards are the second new pattern (no settings cards exist).

**Best for:** surfacing problems people don't come looking for, like expired or
never-expiring tokens. It's the only direction that tells you something before you ask.

---

## Open questions for the pick

1. Is the problem mostly structure (P1) or content (P2)? Flip P2 off in each direction.
   If the directions stop feeling different, it's content, and Tabs is enough.
2. Do Preferences belong in their own section? Flip `prefs` and compare Profile in Side
   nav or Tabs.
3. Is the overview's "tells you before you ask" worth the extra click? It could also
   become a summary strip on top of another direction instead of a page of its own.
