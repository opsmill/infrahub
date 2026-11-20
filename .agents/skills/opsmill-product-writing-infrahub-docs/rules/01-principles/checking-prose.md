# How to review prose

**A clean grep is not a prose review.** A ten-check grep script was built for these rules, run over a
page, and reported every check passing — on a page carrying three actor problems, because
`determines` was not in the list. Neither were `suits`, `appears`, `becomes` or `affects`. The report
was handed to the user as verified.

Review in three layers. Run them on new and rewritten prose, not over the whole page every time.

## 1. Read for meaning and causality

For each paragraph:

- Is it clear who controls the action, and what Infrahub does on its own?
- Are definitions and properties written as definitions, rather than bent into second person to
  satisfy a rule?
- Is a metaphor carrying technical meaning?
- Could a reader take a phrase literally and misunderstand what the product does?

Then walk the subjects. **For every sentence in the new or rewritten prose, write out the sentence's
grammatical subject and its verb, and check whether that subject can perform that verb.** Every
sentence, not the ones that already read oddly — the failure this file opens with is that the three
bad sentences did not announce themselves, which is why a list is the method and attention is not.

Your attention narrows while writing, so producing the list is what puts all of the sentences through
the test. The list is the artifact. Write it to a file beside the outline — `dev/specs/docs/<slug>.checks.md`
in Infrahub main, next to the outline at `dev/specs/docs/<slug>.md`, and left uncommitted like it —
so that a reviewer who asks for it gets a file, not a number. It is what you cite, by count and by
path, when you report what you checked, and a report with no list behind it is the "verified" claim
that was wrong before.

The subjects that come back wrong are always the same kind — a read, a query, a branch, a timestamp,
a diff, a gap, "they", "the two" — which is why the subject is what you look at. The verbs vary every
time, which is why no word list catches them.

| Subject that cannot act | Rewritten |
|---|---|
| The branch **determines** which timeline you read along | **You choose** the branch to say which version of the data you want |
| The web interface **suits** interactive investigation | **Use** the web interface for interactive investigation |
| That gap **appears** throughout ordinary work | **You run into it** throughout ordinary work |
| Three parsing behaviors **affect** which instant you get | **Watch for** three parsing behaviors |

[actors-and-causality](actors-and-causality.md) has the ways out and the worked pairs. Note there
that a feature or an attribute *is* the right subject for a definition or a genuine property.

**Then walk the verbs, the same way.** For every non-technical verb or expression in the new or
rewritten prose, write it down next to the sentence it came from and put it through the four
questions in [voice-and-tone](voice-and-tone.md)'s check. Same file, second list, cited the same
way.

The verb walk exists for the reason the subject walk does. Figurative usage is open-ended, so no
word list catches it, and the case under "Figurative verbs" in [failure-modes](failure-modes.md)
survived repeated readings of the page it was on. Writing out the verbs you used is the only pass
that does not depend on a phrase looking wrong to you.

The two walks answer different questions: the subject walk asks whether the actor can perform the
verb, the verb walk asks whether the word means what it says. A sentence can pass one and fail the
other, so both lists go in the file and both counts go in the report.

Neither walk is a licence to flatten ordinary English. Both produce candidates rather than verdicts:
apply the test to each one, then keep the sentence where the meaning is unambiguous and it reads
well.

## 2. Read for naturalness

Read the page continuously rather than sentence by sentence.

- Does it sound like an experienced practitioner explaining the product to another one?
- Have several sections opened with the same construction because of a rule?
- Has second person become repetitive?
- Did an imperative replace a clearer definition?
- Did a rewrite get more awkward in order to fix an "actor"?
- **Does a sentence say nothing?** Ask what the reader knows after it that they did not know
  before. "A sentence that says nothing" in [failure-modes](failure-modes.md) has the forms and the
  worked pair.

If a sentence is accurate, clear and natural, do not rewrite it to match the shape of another one.

## 3. Run the mechanical checks

grep and Vale, for what they are good at: the fixed word lists, `config` and `repo`, terminology,
identifiers, headings, lint. Treat a clean result as one input to a page you have also read.

## A rewrite is new prose

Restructuring a section regenerates its sentences from the idea, so the output has never been
reviewed, whatever state the input was in. **Review every revision of every changed paragraph before
the user sees it.** Fixing the instance the user named and returning the document is how the same
problem comes back four times in a row.

## Tables get the same pass

Headers and cell values are prose. They escape review because they read as data.

A vague header also hides a wrong value. `You want | Branch | Time` survived several passes, and
underneath it sat `the incident window` — wrong, because a query resolves to a single timestamp and a
window is what a diff takes. Naming the column `State to read | Branch | Timestamp` exposed the
error.

## Report what you checked, not a verdict

Say which checks ran and by what method, and cite both layer-1 walks by their counts and their path.
"Markdownlint reports 0 issues; the build passes with no broken links; in
`dev/specs/docs/ipam-overview.checks.md` I listed the subject and verb of all 41 new sentences and
rewrote 3 where the subject could not perform the verb, and the 26 non-technical verbs I used and
replaced 2 that were carrying technical meaning; I read the page through for naturalness" is a
report. "Clean" is a claim, and once it has been wrong it carries no
information.

A report that describes either walk without a count means that walk was skipped.
