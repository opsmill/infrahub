---
paths:
  - "changelog/*.md"
---

# Changelog entries

Every file here is a Towncrier fragment that is published verbatim in the product's release
notes. The audience is people who run and use Infrahub, not the people who wrote the patch.
They read it to answer one question: does this change affect me, and what do I do differently
now?

Mechanics (naming, change types, `towncrier create`) are covered by the
`creating-changelog-entries` skill and `docs/docs/development/changelog.mdx`. This rule is about
what the text says.

## Write for the user, not the reviewer

State the change in terms of what a user sees, does, or no longer has to work around. A reader
who has never opened the codebase must be able to tell whether the entry concerns them.

- For a fix: what went wrong from the outside - what looked broken, was rejected, was slow, was
  silently lost - and that it no longer does.
- For a feature or change: what is now possible, and anything the user must do differently
  (a changed default, a new field, a value that is no longer accepted).

Frame it around the user-facing surface they already know - the UI, the API and its fields, the
CLI, branches, schema, the upgrade - not around the internals that implement it.

## Leave the implementation out

Skip module paths, class and function names, internal services, database and query details,
and the shape of the fix. If a detail only makes sense to someone reading the diff, it does not
belong in the changelog. That reasoning belongs in the commit message, the PR description, or
`dev/knowledge/`.

Avoid:

- "Refactored the branch-diff resolver to short-circuit on empty payloads."
- "Fixed a `None` dereference in `SchemaBranch.process_inheritance`."

Prefer:

- "Fixed the diff view timing out on branches with no changes."
- "Fixed an error when saving a schema where a node inherits from a generic."

## Say why it matters when it isn't obvious

One extra sentence is worth it when the user cannot otherwise judge the impact: which
installations are affected, whether data was wrong in a way they may still be looking at,
whether anything happens automatically on upgrade, or what they need to do. Skip it when the
first sentence already answers "does this affect me?" - length is not the goal, and an entry
that pads a one-line fix reads as noise.

## Style

- Past tense, describing the change as shipped ("Fixed …", "Added …", "Removed …").
- Start with the change, not with the context that led to it.
- One sentence by default. Only go longer for the impact above, and keep it plain prose.
- No issue numbers or PR links in the body. The filename carries that reference: the part before
  the change type is the GitHub issue the change closes (`1234.fixed.md`), and Towncrier turns it
  into a link appended to the rendered entry. A change with no issue behind it uses the `+`
  prefix and a short slug instead (`+block-user-branched-from.fixed.md`), which renders with no
  link. Either way, don't restate the reference in the text.
- Refer to things by the names the product uses in the UI, the docs, and the API.
