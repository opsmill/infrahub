# Make causality clear

The aim is accurate causality, not a preference for active or passive voice, and not a rule about
which words may be sentence subjects. Choose the subject that makes the meaning easiest to follow.

Four subjects are each right in different places.

## The reader

Use the reader when describing an action or a decision they perform.

> Reference the Python Transformation from the schema.
>
> Choose Jinja2 when the calculation needs only direct relationships.
>
> When you compare two branches with the same schema, Infrahub returns an empty schema diff.

## Infrahub

Use Infrahub when describing automatic product behavior.

> Infrahub recalculates the value when a relevant input changes.
>
> If you request a time earlier than the history available to a branch, Infrahub rejects the query
> rather than returning partial data.

What goes wrong here is not Infrahub being the subject; it is Infrahub being credited with an
outcome the reader achieves. "Infrahub Sync keeps your data aligned across tools" is a value claim
in a mechanical sentence's clothing. "Use Infrahub Sync to keep data in sync across tools" gives the
work back to the reader.

**The tell:** *keeps, helps, turns, lets, empowers, enables, makes it easy*, with the product as
subject.

## The feature, object, or concept

A feature, an object, an attribute, a query, or a branch is the natural subject when you are saying
what it **is**, what it **contains**, or a property that genuinely belongs to it.

> A computed attribute is a read-only `Text` or `URL` value.
>
> Python computed attributes run asynchronously on workers.
>
> The `at` argument accepts a timestamp.

Do not rewrite these into second person to satisfy a rule about actors. "A computed attribute is a
read-only Text or URL value calculated from data already modeled in Infrahub" is a better sentence
than any version that makes the reader the subject.

## A condition or state

Lead with the condition when that is what the reader needs to notice.

> On a branch other than the default, a new object remains isolated until that branch merges.
>
> On the default branch, the earliest available timestamp is the branch creation time.

Take care that the state is one you have verified. A condition invented so the sentence has a
subject reads as authoritative and is not.

## The test

Ask: is it clear what the reader controls, what Infrahub does on its own, and what is simply a
property or a definition?

If yes, the causality is clear. That is the whole requirement.

## Where causality actually goes wrong

Not in feature-as-subject sentences, which are usually fine. It goes wrong when the subject cannot
perform the verb and the sentence hides who acted:

> ❌ Four interfaces create objects.
> ✅ There are four ways to create an object one at a time.

The branch-and-timestamp pair that started this rule is written out once, under "Causality is
unclear" in [failure-modes](failure-modes.md); [checking-prose](checking-prose.md) has the four
subjects from the same page that a grep passed.

A version, a release, or a page is the clearest case — none of them does anything:

> ❌ Infrahub 1.11 records those dependencies.
> ✅ Attribute values and relationship edges each carry the interval during which they were current.
>
> ❌ This page explains how object files work.

Three ways out, when a subject cannot perform its verb: give the verb to the reader, give it to
Infrahub where the behavior is automatic, or lead with the state.

Related: do not use an abstract noun as the collective term for concrete things the reader has just
been shown. "The other three accept the same values" beats "the other interfaces accept the same
values".

## Naming the reader

Use second person when you are describing the reader's action, choice, or result. Use third person
when discussing organizations or roles, or when second person would sound forced.

| Forced | Natural |
|---|---|
| "Teams use Infrahub Sync to migrate…" | "Use Infrahub Sync to migrate…" |
| "Users can configure…" | "Configure…" |

"Each team controls cadence and retry behavior" is fine — it describes how different organizations
work, not a reader action. So is a definition with no reader in it at all.

The imperative is stronger when the action is the point: "Define a sync project" beats "You define a
sync project". Use "you" for what the reader *has* or *sees*.

## A technique for a behavior that is hard to explain

When product behavior is difficult to describe, it can help to separate three things:

1. what the reader does;
2. what Infrahub does;
3. what result or condition follows.

> When you add a timestamp to a query, Infrahub evaluates each requested object using the attribute
> values and relationships that were valid at that time.

Use this when it makes causality clearer. It is a diagnostic for a stuck sentence, not a standard
shape — a page where every sentence follows it reads as generated.

## Vary the construction

Definitions, explanations, choices, and instructions are different jobs and take different sentence
shapes. Read your sections in sequence, and if they have fallen into one pattern, vary it. Do not
rewrite a sentence that is accurate, clear, and natural to make it match the shape of another one.
