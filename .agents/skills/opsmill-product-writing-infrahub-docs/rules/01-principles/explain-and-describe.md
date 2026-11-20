# Explain and describe

**Applies to every page, not only overviews.** This file used to live inside
[overview-page-content](../03-patterns/overview-page-content.md), which meant a writer who had
classified their page as a how-to never reached it. That is how a page ships accurate and hollow:
every claim sourceable, every rule obeyed, and nothing on it that helps a reader decide anything.

A page that states only what is verifiably true can still fail its reader, because knowing what
something does is not the same as understanding why it works that way or when it will matter.

So explain. Give the reasoning behind a design choice, the consequence of getting something wrong,
the comparison that locates a concept against something the reader already knows. Reason from your
sources to do it — that is analysis, and it is the substance of good documentation.

## What keeps it honest

- **Reason from sources, and say when you have.** An explanation built on what the code, briefs and
  docs establish is legitimate content. Mark the parts you inferred so a reviewer confirms the
  substance rather than the wording.
- **Product behavior stays strict.** Versions, defaults, limits, flags and API arguments come from
  the code or the docs. Reasoning applies to why something matters; what it does comes from the
  source.
- **Explanation earns its length; assertion does not.** "Schema migration sequencing matters because
  an attribute made mandatory before its data exists rejects every write" teaches. "Schema migration
  is important" occupies the same space and teaches nothing.

The test is what the reader can now do. After an explanatory passage they should be able to make a
judgment they could not make before: choose between two options, anticipate a failure, or recognize
that the feature does not apply to them.

## Include a mechanism when it changes what the reader does

Explain how something works when knowing it helps the reader predict behavior, choose between
options, understand a result, troubleshoot, or understand a limit. Use the shape:

The shape is `situation → mechanism → practical consequence`.

> Relationships are versioned as well. A query for a specific timestamp therefore returns both the
> attribute values and the object relationships that were valid at that time. This is important for
> topology and dependency questions where the connections between objects are part of the answer.

Situation, then what the product does, then what it means for the reader's work.

**One exception, and it matters.** When the mechanism produces a *constraint* the reader must obey,
state the rule first and the mechanism second. A reader who breaks the rule needs to recognize the
error before they need to understand its cause:

> You can query a branch back to the point where its history begins. If you request a time earlier
> than that, Infrahub rejects the query rather than returning partial data.
>
> When you create a branch, Infrahub records where it diverged rather than copying the entire
> dataset. …

Keep the length proportionate to what the reader does with it. A long account of how a class of
database works does not help someone perform the task, and belongs in a blog.

## Separate the general capability from the source's use case

Source material usually explains a feature through one compelling scenario. Use the scenario; do not
let it redefine the feature.

The naming-conventions blog gives four good examples — generated hostnames, interface descriptions,
formats legacy systems expect, different representations for different audiences. All four are names.
Computed attributes are broader: any `Text` or `URL` value that can be calculated from modeled data
and should stay in step with it. A page built only from that post reads as though the feature exists
for naming.

Find the rule that makes each example an example of the same thing, state the rule, and then use a
few examples to make it recognizable. Four variations of one scenario leave a reader thinking the
feature only does that.

## The guard

This licence loosens one constraint, and the failure it invites is spending the new room on
persuasion. The restraint rules apply here unchanged. Three failures arrive dressed as explanation:

- **An implied competitor.** "Most tools force you to choose between X and Y" describes an unnamed
  alternative. State what Infrahub does.
- **Rhetorical shape.** Antithesis, tricolon, and setup-then-reversal are promotional cadence even
  when every word is clean. Explanation reads as reasoning, not as a line from a keynote.
- **A dramatized problem.** Sharpening the stakes so the answer lands harder is selling the fix.
  Describe the situation at its real size.

If a passage would work in a keynote, it is positioning wearing explanation's clothes. Teaching
survives being read flatly.
