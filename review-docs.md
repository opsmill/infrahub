# Docs review

Apply these checks when the pull request changes a file under `docs/`, or changes behavior a user can
see in the UI, the API, the CLI or the configuration. Skip them for any other pull request.

Docs findings are Nit at most, so they share the five-Nit cap. Rank them in this order: a docs sentence
the code contradicts, a missing docs update, then language. Put the rest in the list at the end of the
summary.

## Missing docs updates

- When the pull request changes behavior a user can see, find the page under `docs/docs/` that
  describes it. If the pull request does not update that page, name the page's path in the summary and
  quote the sentence that is now wrong, or say what is missing.
- When the pull request deletes or renames a published page, check that `docs/redirects-pending/` has
  an entry for its old URL.
- When a page imports a file from outside `docs/`, check that the `docs` stage of
  `development/Dockerfile` has a `COPY` line for that file. The docs build passes without it and the
  container image build fails.

## Facts on changed docs lines

- Check each claim against the code on the base branch: attribute kinds, GraphQL fields, defaults, and
  the text of UI buttons and labels. Cite the source line.
- For `infrahubctl` and SDK claims, the source is the commit that the `python_sdk` submodule pins, not
  the tip of an SDK branch.

## Language on changed docs lines

Vale already checks spelling, heading case, the case of product terms, "simple" and "easy". Report
only the problems below. Quote the sentence and give the rewrite.

- A subject that cannot perform its verb, such as a version, a release or a page. Give the verb to the
  reader, to Infrahub when the behavior is automatic, or lead with the condition.
  - ❌ Infrahub 1.11 records those dependencies.
  - ✅ Attribute values and relationship edges each record the interval during which they were current.
- Infrahub credited with an outcome the reader achieves, with verbs such as keeps, helps, lets,
  enables or "makes it easy".
  - ❌ Infrahub Sync keeps your data aligned across tools.
  - ✅ Use Infrahub Sync to keep data in sync across tools.
- Figurative words. Many readers read English as a second or third language, so write the literal
  word: "has", not "carries"; "is stored on", not "lives on"; "traverse", not "walk"; "as it was", not
  "as it stood".
- Marketing language: a sentence that names the category a feature belongs to instead of what it does,
  three or four benefits in a row, a comparison with an alternative nobody named, "out of the box"
  (write "by default"), "purpose-built", "seamless".
- A sentence that adds no fact: "this page covers", "it's worth noting that", or a transition that
  announces a difference instead of stating it.
- "just" used to make a step sound small.
- "node" for a populated instance in user-facing text; write "object". "Node" stays only where it names
  the schema kind that pairs with "Generic".
- A general word used for a named Infrahub concept, such as "proposal" for a Proposed Change, or
  "repository" for a linked repository.
- Numbered steps outside a how-to guide, or guide steps and topic explanation mixed on one page.
