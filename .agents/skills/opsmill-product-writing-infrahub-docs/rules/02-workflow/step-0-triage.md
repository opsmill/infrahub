# Step 0 — Triage and inputs ★

## Contents

- [Ask the user one question, then classify the work yourself](#ask-the-user-one-question-then-classify-the-work-yourself)
- [Asking for material — new feature docs and reorganizations](#asking-for-material--new-feature-docs-and-reorganizations)
- [Classify what the user handed you — spec, draft, or source](#classify-what-the-user-handed-you--spec-draft-or-source)
- [Outline routing](#outline-routing)

Work out what kind of work this is and what material exists, before creating a branch.

**The label you pick here does not decide what you may change.** It names the job so you and the
user can talk about it. What the work actually covers is agreed at [Step 3](step-3-outline.md),
once the page has been read and the research is done. Calling something a smaller update and
treating that as permission to look at one section is how a page ends up with a good new opening
sitting directly on top of its weakest paragraph.

## Ask the user one question, then classify the work yourself

Ask the user which of these they want, in their terms:

1. An update to an existing section
2. A new section or feature
3. A reorganization or migration of existing docs

That is the only classification question they should have to answer. **Which kind of work it is, and therefore how much of the workflow runs, is your judgement, not theirs.** Take their answer, then investigate: read what they gave you, read the existing pages around it, look at how much is actually missing. Then decide, and tell them which kind of work you have chosen and why, by name.

| Use case | What it is | What changes in the workflow |
|---|---|---|
| **1. Update to existing content** | An existing page needs an addition, a correction, or a refresh, and the framing for the feature already exists in the docs | Light on inputs. Ask which page, what changes, and where the content comes from, then start. The audit at [Step 2](step-2-audit.md) still reads the whole page, and [Step 3](step-3-outline.md) still runs — for a small change it is a few lines. |
| **2. New feature or section** | A feature or section has no docs yet, so what the page is for and when to use it has to be established | Full workflow. Ask for the material listed below, research comparable products at Step 2.7, produce an outline at Step 3 and get it agreed. |
| **3. Reorganization or migration** | Existing content moves to a different structure | Full workflow, with the audit at Step 2 covering everything being moved. |

**A smaller update usually needs little material from the user, and that is fine.** If someone asks you to document a new attribute on a feature that is already documented, the answer to "why would anyone use this" already exists on the page. Read it, match it, make the change.

**"Little material" is about what you ask the user for, not about which rules you read.** [What the smaller-update shortcut covers](../../SKILL.md#what-the-smaller-update-shortcut-covers) sets out what it shortens and what it never skips.

**Ask when you are short of something you need, whatever the size of the work.** The point of the checks below is to avoid a ceremonial interview before an easy change, not to make a smaller update proceed on guesswork. If the page does not establish why the new attribute matters, or the code leaves the behaviour ambiguous, or you cannot tell which of two readings the user intended — ask, and say what you are missing and why it matters. One specific question beats a page with a hole in it.

**Where the line is.** Some work arrives described as small but is not:

- **A brand-new page counts as new feature docs**, even when the request sounds small, because a new page has to say what it is for and nothing existing establishes that.
- **If the only source is a pull request, a branch, or the code**, it is new feature docs. Code shows how something behaves, not when anyone would want it.
- Otherwise, an addition to an existing page is a smaller update.

**Say which kind of work you chose and why, using its name.** Tell the user this is a smaller update, new feature docs, or a reorganization — not a number. When the choice is made silently, whole phases of the workflow get skipped without anyone having decided to skip them.

## Asking for material — new feature docs and reorganizations

**Show the list once and ask for whatever they have.** One message, not an item-by-item interview, and work can start before every line is filled. Most of the time the user will hand over two or three things and that is enough to begin.

Something like: "Anything you have on this would help — a brief or product card, a spec or the code, notes or a transcript from a discussion, an existing outline, or related pages I should match. Whatever you have is fine, I will tell you if something turns out to be missing."

Then start researching. **Come back with specific requests, not a general one.** A follow-up that names the gap gets a useful answer; a checklist does not:

> "I have the code, so I can describe how it works. Nothing tells me why a team would choose this over the manual approach, and NetBox's equivalent page covers that. Is there a brief or a customer conversation, or can you tell me in a sentence?"

That is the difference between asking someone to fill in a form and asking them a question only they can answer.

The material worth having, when it exists:

### Product framing (what + why)

- **Product brief** — what is this feature, who is it for, what problem does it solve? Notion page or file.
- **Messaging brief** — positioning, value props, jobs-to-be-done. Notion page or `.docx`. An internal document, and much of it is plain description; the test is whether a sentence educates or persuades, not where it came from. See [voice-and-tone](../01-principles/voice-and-tone.md).
- **JPD card** — Jira Product Discovery card or equivalent. Captures the problem statement, customer signal, and scope decisions.
- **Discovery / product brief from customer conversations** — interview summaries, use-case docs.

### Engineering context (how)

- **Spec / design doc** — feature spec, RFC, ADR, or engineering design document.
- **Spec-kit artifacts** — `spec.md`, `plan.md`, `tasks.md` if the feature came through the spec-kit flow.
- **Source code** — the slice of the repo that implements the feature (backend module, frontend pages, schema definitions, CLI commands). Authoritative for product facts; not authoritative for product positioning.
- **Schema additions** — new node kinds, attributes, relationships, generics, permissions.

### Discussion artifacts (decisions and nuance)

- **Customer interview transcripts** — recordings or transcripts of conversations with users that informed the feature.
- **Internal meeting transcripts** — design reviews, product team syncs where this feature was discussed. Often capture trade-offs and the "why we did X not Y" that no spec records.
- **Slack threads with key decisions** — paste the canonical thread if one exists.

### Marketing / external (positioning calibration only — not docs prose)

- **Blog posts** — drafted or published announcement posts. Often the clearest statement of why a capability exists and which situations it addresses, which makes them a good source for the framing a page needs. Take the parts that explain the product and leave the argument; [Step 2.7](step-2.7-content-audit.md) has the test.
- **Demo videos / screencasts** — for the canonical user flow.
- **Sales decks or one-pagers** — useful for understanding which capabilities are being highlighted.

### For the docs themselves

- **Feature / solution / section name** + a one-line description of what's being shipped.
- **An existing outline or agreed structure** — a document, a ticket, a decision recorded somewhere, or a few lines the user pastes in. It does not have to be formal; if someone has already decided the shape, that decision is the spec. See "Outline routing" below.
- **Related existing docs** — adjacent features in the same section, for tone calibration per [voice-and-tone](../01-principles/voice-and-tone.md).
- **Target sidebar location** — if the user already knows where it lands. Otherwise the [navigation map](../04-infrahub/docs-navigation-map.md) decides at Step 3.

### What to do when something is missing

These gaps matter because of what they cost the reader, not because a list is incomplete:

- **Nothing explains why the feature exists** (no brief, no card, no discussion notes) — the page will describe how it works and never say when anyone would use it. Ask for whatever exists, or ask the user to tell you in a sentence. A verbal answer is enough.
- **No spec and no code** — the page may state behaviour incorrectly. This one is worth stopping for, because being wrong is worse than being thin.
- **Only marketing material** — the page will read as positioning. Ask for the code or the spec.

**Name what is missing, both in the moment and in the pull request description.** Given only a pull request or the code, it is easy to write a page covering the mechanics and present it as finished, leaving the user unaware that the "when would I use this" part is absent. Say it plainly instead, before drafting:

> "I have the code, so I can describe how it works and give accurate examples. I cannot say when someone would choose this or how it compares to the alternatives, because nothing I have covers that. Do you have a brief or notes, or can you tell me in a sentence?"

If nothing exists and the user asks you to proceed, that is a reasonable decision — write what you can, and record what is absent in the pull request as a question for whoever reviews it ([Step 2.7](step-2.7-content-audit.md)). Docs that only cover mechanics are sometimes the right scope. Docs that only cover mechanics **without anyone being told** never are.

### A smaller update needs almost none of this

For an update to a page whose framing already exists, ask for three things and start:

- Which page
- What needs to change, and why
- Where the new content comes from — the code, the schema, a screenshot, or a sentence from the user

That is usually enough, and a brief or a transcript is usually more than the work needs. Ask for more the moment you find you need it — because the page does not already establish the framing, because the source is ambiguous, or because the change turns out to introduce a genuinely new concept rather than extending an existing one. In that last case, reclassify it as new feature docs.

## Classify what the user handed you — spec, draft, or source

When the user gives you a document, work out which of these it is before deciding what to do with it. They are easily confused, and confusing them causes the worst outcome: the user's text ends up in the docs almost unchanged, with none of the review, research, or voice work done.

| What it is | How to recognise it | What you do with it |
|---|---|---|
| **A structural outline** | Describes pages, where they go, and how they are organised | The structure is decided. Check it at Step 2.5, add recommendations from your own research, then draft at Step 4. Its wording is not the docs wording. |
| **Draft content** | Reads like documentation — paragraphs written for readers | **Source material, not finished docs.** It goes through the same process as anything else: review at Step 2, research at Step 2.7, drafting under the voice rules, and the pre-PR audit. What you hand back is your revision with the changes explained, not their text moved into place. Facts written by someone who owns the feature are reliable input ([Step 2.7](step-2.7-content-audit.md)); their phrasing still goes through the voice rules. |
| **Raw sources** — specs, briefs, transcripts, code | Facts and background, not text written for readers | Material to work from. |

The sign that this has happened: the diff shows the user's document with formatting changes and little else. If a draft they supplied genuinely is already correct, that is a conclusion to reach *after* reviewing it — say so explicitly, and show what you checked.

## Outline routing

- **If the user provides a structural outline**, the structure is already decided, so do not produce a competing one. Your job is two things instead. **Check it** against the skill's rules at [Step 2.5](step-2.5-spec-review.md) — placement, page shapes, missing child pages, anything that will not work. Then **add recommendations** from research its author may not have done: read the adjacent pages in that section, and read how two or three comparable products handle the same subject ([Step 2.7](step-2.7-content-audit.md)). Bring back a short list of what you would add and why, with the source for each. Then draft at Step 4.

  An agreed outline is not necessarily a complete one. It settles where things go, usually says nothing about how deep each page should be, and may predate content that now exists elsewhere in the docs.

- **If the user provides draft content**, it is not an outline. Run the full process: review the draft at Step 2, research at Step 2.7, then propose your revision with the changes explained.
- **If there is no outline**, continue to Step 1, then the Step 2 review, then produce an outline at Step 3 for the user to agree before you draft anything.

★ **Gate:** present these separately rather than as one question:

1. **Which kind of work this is, and why** — named, not numbered: a smaller update or improvement, new feature docs, or reorganizing existing docs. Your decision, based on what they asked for and what you found, not a question back to them.
2. **What you have and what is missing** — only for new feature docs and reorganizations, and only the gaps that matter. Name each gap, say what the page will not be able to say without it, and ask the specific question that would fill it. If nothing is missing, say so and move on.
3. **Which route the workflow takes** — Step 1 → 2 → 3, or Step 1 → 2.5 → 3 when an outline already
   exists. Step 3 runs either way: it is where the scope is agreed, and for a small change it is a
   few lines rather than a document.
4. **How many pull requests** — normally one covering the whole scope. Confirm it at the Step 3 outline gate once the scope is clear, rather than raising it twice.

Say what you will produce at each following gate. For new feature docs, draft after the user has answered or waived the gaps in item 2. For a smaller update, this gate can be a single short message; do not manufacture questions to fill it. It is still a separate message from the gates that follow it, and it still ends with the "Rules read" line from [gate-discipline](../01-principles/gate-discipline.md).
