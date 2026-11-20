# Steps vs. explanatory sections (how-to guides)

A how-to guide can be written as numbered steps or as explanatory sections. Pick based on whether the task has a real order — not by habit, and not by copying a sibling page.

## The test

**Do the parts have genuine dependencies and a single end-state, or are they independent operations with sequence numbers attached?**

- **Dependency-ordered, one outcome → numbered steps.** The reader runs it once, top to bottom, and each part depends on the previous. Configuration procedures are the typical case: collect inputs → configure the connection → set credentials → enable → validate. You cannot validate before enabling. Numbered steps are correct here, and Diátaxis allows a how-to guide to be sequential.
- **Independent operations → explanatory sections.** Each part stands alone and the reader arrives needing only one of them. "How to create X", "how to assign X", "how to edit X" have no forced order; numbering them implies a linearity that isn't real. Use `## How to <operation>` sections the reader can jump between.

**Reorder test:** if you can reorder the parts, or do one without the others, and it still makes sense — they are sections, not steps.

## Not the same as the tutorial test

[tutorial-shape-test](tutorial-shape-test.md) decides whether something belongs in Academy as a *tutorial*. This rule decides the shape of a *how-to guide* that is already correctly placed. A guide can be legitimately step-numbered (a setup procedure) without being a tutorial — no running scenario, no narrative arc, no "by the end you'll have built…" closer. Step headings alone are one signal of four; they do not make a page a tutorial.

## Consistency within a section

When sibling pages document parallel tasks (for example `configure-sso` and `configure-ldap`), keep their shape consistent. Switching a configuration guide from numbered steps to explanatory prose is a section-wide decision — change the matched set together, don't diverge one page and leave the rest.

## Precedent

The LDAP and SSO configuration guides use dependency-ordered numbered steps correctly: setup is run-once and ordered. The Profiles tutorial dropped on PR #9114 was the opposite error — independent feature operations with sequence numbers bolted on.
