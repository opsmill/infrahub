# Audit rigor

Build + lint passing is necessary but not sufficient. Factual claims need a source. Invented content is always wrong. Cross-links need to resolve.

**This rule is repo-agnostic.** Applies wherever docs are written.

## The audit is a real read-through, not a tool run

Build + markdownlint + Vale + word-check are necessary but not sufficient. They catch syntax problems and policy violations, not factual drift or content gaps.

The audit means **reading every new/modified file end-to-end with the source content open alongside**, looking for:

- **Extraction faithfulness** — did the new spoke preserve every claim from the source?
- **Hub coherence** — does the hub still read as a complete concept page after the spokes were extracted?
- **Invented content** — did you write anything that has no analog in the source?
- **Cross-link target accuracy** — does each link land on the right page and section?

If the audit feels short, you're not doing it.

## Source every factual claim

For each factual claim in new prose, find a source: existing docs (current topic, guide, reference, schema specs, related feature docs), schema definitions, code comments. If a claim can't be sourced, flag it.

Two habits make this rule leak:

**Read the whole file, not the fact you came for.** Opening a source to confirm one claim and stopping there leaves the rest of that file unread, including the parts that contradict what you are about to write. A docs page that told readers the UI time selector used UTC cited the correct component for two neighbouring facts; the missing timezone prop was a few lines away in the same file, and nobody read down to it.

**Text carried over from an existing page is a claim, not a given.** Wording inherited from a page you are not editing gets read as already-verified, and it is often the oldest and least-checked prose in the section. The UTC error above was copied from an unpublished tutorial. Verify what you keep on the same terms as what you write.

## Cross-link verification

Run `grep -rln '<feature-slug>' docs/docs/` (or the equivalent for your repo) to find inbound references. For each match:

- Fix immediately if it's within the feature being migrated.
- Log to the redirects-pending `cross_links_to_update` section if it's in another feature/section.

## Delegate a large audit

For a section-wide migration covering ten or more pages, hand the audit to a subagent with a focused brief. It can read everything at once and return a structured list of findings, which is both faster and more thorough than working through the pages one at a time.

A clean build and a passing lint are not an audit. They check syntax and policy, not whether the content is accurate or complete.

## Report format

Report findings with specific file paths + line numbers:

- `groups/use-in-automation.mdx:54` — the claim that a Generator owns a `CoreGeneratorGroup` is wrong; per `generators/overview.mdx`, the SDK manages it automatically.

## Examples are claims too

An example that states product behaviour is a claim, and it gets sourced like any other. This is the
easiest place for an invented fact to survive, because a rules file is not the page anyone
fact-checks, and because the ✅ side of a pair is read as the correct version by definition.

An audit of this skill found five: an interrupted merge "recoverable with one command", a merge that
"no longer blocks branch creation", a uniqueness scan that "now completes", Infrahub recomputing all
computed attributes when the affected set is unknown, and definitions storing "a content fingerprint
of their inputs". None could be sourced. Each sat on the correct side of a pair, teaching that the
way to replace a vague claim is to invent a specific one.

Prefer an example you verified while writing a real page. Those come with a file and a line number,
and they stay true.

## Opening and summary sentences are claims too

The sentence that introduces a section is a claim about what the section contains, and it is
generated from an impression of the material rather than from the material itself. That is what makes
it the easiest place for a contradiction to survive: the details underneath carry file and line
numbers, and the sentence above them carries nothing.

A section on how far back a branch can be queried opened by saying each branch can be read back to
the point where its own history begins, then explained four paragraphs later that the limit is
always the default branch's creation time. The second statement was verified against
`query_time_validator.py`. The first was written from a general sense of what the section was about,
and contradicted it. No code was needed to catch this — only reading the two sentences together.

**Write a section's opening claim from the same source as the details beneath it.** If the paragraphs
cite a file and line, the sentence introducing them answers to that file too. A summary that cannot
name the source its own section rests on is a claim with no source, which the rule above already
forbids.
