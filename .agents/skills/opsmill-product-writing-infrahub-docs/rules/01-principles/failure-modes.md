# Patterns worth reviewing

Weaker constructions and stronger versions of the same idea. **These are not bans on grammatical
patterns.** Each entry explains why the weaker version is less useful; a construction named here can
be the right choice elsewhere.

The single copy of this list. The drafting self-review ([Step 4](../02-workflow/step-4-create-files.md))
and the pre-PR audit ([Step 9](../02-workflow/step-9-pre-pr-audit.md)) both check against it, and
[voice-and-tone](voice-and-tone.md) holds the rules these failures break.

The first group carries a worked pair, because the fix is not obvious from the name of the failure
and an abstract instruction — "use the product's own verb", "state the capability" — gives you
nothing to reach for. The second group is named and left there: "write 'you' instead of 'teams'"
needs no demonstration.

## Where the fix needs showing

**Causality is unclear.** Something is the subject that cannot perform the verb, so the sentence
hides who acted.

> ❌ The branch determines which timeline you read along, and the timestamp determines which point on it.
> ✅ You choose the branch to say which version of the data you want, and the timestamp to say when.

A feature, an object or an attribute as the subject is not the problem — "a computed attribute is a
read-only `Text` or `URL` value" is the right sentence. The problem is a subject doing something it
cannot do. Versions, releases and pages are the clearest case: "Infrahub 1.11 records those
dependencies" has no actor in it.

[actors-and-causality](actors-and-causality.md) has the three ways out and the worked pairs.

**Value stated as an absence.** Name the mechanism that delivers the value; the absence is then
implied.

> ❌ Sync data without writing custom integration code.
> ✅ Sync data using pre-built adapters.

Contrasting two mechanisms is fine — "you query that data directly rather than reconstructing it
from a backup" names one. What to avoid is value that exists only in the absence. The same applies to
"no need to", "instead of having to" and "you don't have to". Where the absence genuinely matters,
put it in a section about what is not included, not in the value prose.

**A generic verb propped by an adverb.** Strip the adverb; if the verb stops doing work, name the
operation instead.

> ❌ Keep Infrahub continuously aligned with another source of truth.
> ✅ Keep Infrahub in sync with another source of truth.

"Aligned" survives only because "continuously" holds it up. "In sync" is the product's word for a
defined operation, which is why it carries the meaning alone.

Watch for *align, ensure, maintain, drive, leverage, enable, facilitate, optimise, streamline*. None
is banned — the pattern is what to catch.

**Figurative verbs.** Test each against its literal meaning, and against word-for-word translation.

> ❌ Read the graph as it stood at a past timestamp.
> ✅ Read the graph as it was at a past timestamp.

"As it stood" is the one to watch: it reads as idiomatic English and appeared thirteen times in one
page before anyone noticed.

**A term borrowed from another domain.** Grep the docs before using a word for a product concept —
see "Terms the product already has" in [voice-and-tone](voice-and-tone.md).

> ❌ Infrahub stores a pointer to the moment it diverged.
> ✅ Infrahub records the time it diverged as the branch's `branched_from` timestamp.

**The opening does not orient the reader.** It starts on mechanism, so nobody can tell what the
section is for.

> ❌ When you create a branch, Infrahub records where it diverged rather than copying the entire dataset.
> ✅ You can query a branch back to the point where its history begins.

The mechanism still belongs on the page, as the next sentence.

A definition often *does* orient the reader — "A computed attribute is a read-only `Text` or `URL`
value calculated from data already modeled in Infrahub" is a good opening, because what the thing is
happens to be what the reader needs first. What fails is opening on internals.

**A sentence that says nothing.** Literal, not marketing, and empty. The common form is a transition
that announces a difference instead of stating it.

> ❌ Infrahub tracks what each computed attribute reads. What it tracks differs by kind:
> ✅ Infrahub recalculates a computed attribute when data used by its calculation changes. Jinja2 and Python differ in how precisely Infrahub can tell which data that is:

Also: "keeps it current", "improves consistency", "this section covers". Ask what the reader knows
after the sentence that they did not know before it.

**Messaging-brief patterns.** Positioning sentences, stacked benefits, comparison to an unnamed
alternative.

> ❌ IPAM is a version-controlled, branch-aware capability built into Infrahub.
> ✅ IPAM manages prefixes, addresses, and namespaces, and because changes are branch-aware you can propose an addressing change and review it before it merges.

Four forms recur. **Positioning sentences** name categories the product belongs to rather than what
it does. **Stacked value claims** put three or four benefits in a row, none of them verifiable in a
reader's own instance. **Comparisons to an unnamed alternative** — "you do not run a reconciliation
job" — describe a competitor nobody named; state what Infrahub does. **Vendor idiom** has plain
equivalents: "out of the box" → "by default", "purpose-built" and "ships with" → "Infrahub provides"
or "Infrahub includes".

## Where naming it is enough

- **The reader in third person** — "teams use", "operators run". Write "you", or the imperative;
  [actors-and-causality](actors-and-causality.md) has the worked pairs.
- **Assistant hedging** — "you might want to", "it's worth noting that". Delete the frame and keep
  the statement.
- **Phrases about the content rather than the content** — "the key thing to know", "the headline
  differentiator", "how the pieces fit together". State the fact, or use a heading naming what the
  section documents.
- **Layout-referential phrasing** — "this page covers", "this section describes". State the fact; the
  heading has already announced it.
- **An opener referring to something not yet named** — "Both create objects from…" before either has
  been introduced. Introduce them first.
