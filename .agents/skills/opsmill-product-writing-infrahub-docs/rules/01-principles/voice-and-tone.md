# Voice and tone

## Contents

- [The standard: write like well-regarded open-source docs](#the-standard-write-like-well-regarded-open-source-docs)
- [Terms the product already has](#terms-the-product-already-has)
- [Who is the subject of the sentence](#who-is-the-subject-of-the-sentence)
- [Be concrete: describe how it works](#be-concrete-describe-how-it-works)
- [Marketing register](#marketing-register)
- [Openers, links, and titles](#openers-links-and-titles)
- [Other rules](#other-rules)
- [The recurring failure modes](#the-recurring-failure-modes)
- [Match the section you are writing in](#match-the-section-you-are-writing-in)

**These rules apply to any new prose written with this skill, in any repository.** Voice does not change per repo.

## The standard: write like well-regarded open-source docs

The rules below catch the common failures, but they are not the standard. The standard is the voice used by open-source docs that technical readers actually want to read. Before applying any rule below, ask: **would this paragraph appear on FastAPI, Stripe, uv, or Tailwind?** If not, it needs work, even when it breaks no rule.

| Reference | Why it is the standard |
|---|---|
| **[FastAPI](https://fastapi.tiangolo.com/)** | Direct second-person voice, concrete examples, clear separation of tutorial, how-to and reference. Closest match to our audience. |
| **[uv](https://docs.astral.sh/uv/)** | No filler and no marketing, without simplifying the subject matter. |
| **[Stripe](https://stripe.com/docs)** | The best model for capability statements. Intros say what the tool is *for*, never lead with implementation, never define by negation. |
| **[Tailwind CSS](https://tailwindcss.com/docs)** | Capability stated first. Read the first paragraph of any utility page. |
| **[Docusaurus](https://docusaurus.io/docs)** | Same framework we use, when you need to know how a convention should read. |

Two shapes worth matching. Stripe's introduction — one capability sentence, then "Use it to…" with two specific outcomes:

> "The Payments product gives you everything you need to accept payments online or in person. Use it to integrate a low- or no-code checkout, or use its core APIs directly to build a custom payment flow."

And Stripe's how-to sentence — imperative, three steps, each naming something concrete:

> "To accept a payment, create a Payment Intent, confirm it from the client, and check the result."

**Expect to drift away from this.** The pull is towards marketing language, hedging and over-qualification ("it's worth noting that", "you might want to consider"), third-person paraphrasing of the reader, generic verbs propped up by adverbs, and writing down to the reader by trading the product's own terms for simpler stand-ins. These are assistant-voice defaults, not documentation defaults. The rules below catch the most common ones; the standard above catches the rest, but only if you check against it.

---

## Terms the product already has

Before using a word for a product concept, check whether the docs already use one. Grep the docs
directory for the term. Three outcomes:

- **The docs use it.** Use it too. `timeline` appears throughout `activity-log.mdx` and in the
  release notes as "branch timelines" — it is Infrahub vocabulary and it is available.
- **The docs use a different word for the same thing.** Use theirs. The docs say `query`; there is no
  countable "a read" anywhere in them, so "add a timestamp to any read" was importing database
  vocabulary over the product's own word.
- **Nothing in the docs uses it, because it comes from somewhere else.** Describe the thing instead.
  `pointer` is real Git vocabulary — the docs use it correctly for Git refs — but an Infrahub branch
  stores a `branched_from` timestamp, so "a pointer to the moment it diverged" borrowed Git's mental
  model for something plainer. `coordinates` for a branch-and-timestamp pair was geometry, invented
  on the spot.

The check takes one command and it settles the question. Doing it also tells you when a term you
suspected is legitimate, which is worth as much as catching one that is not.

## Who is the subject of the sentence

Who acts in a sentence — the reader, Infrahub, or a condition — has its own rule: [actors-and-causality](actors-and-causality.md). Read it before drafting. It is the rule most often broken, and the one most often over-applied.

## Be concrete: describe how it works

The audience is international and expert — network and automation engineers, many reading English as a second or third language. The technical vocabulary is not the hard part; LDAP, STARTTLS, `idempotent` and `reconciliation` are shared across languages. The hard part is a common word used in a sense other than its first meaning. Someone who knows that "carry" means to hold and move something cannot reliably decode "this release *carries* breaking changes".

Write the mechanism, in the plainest words that describe it:

- **Use words in their first, literal meaning.** A release *includes* changes. A field *contains* a payload. An API *returns* a code. Objects are *created*; they do not *arrive*. A file is *stored* in Git; it does not *live* there.
- **Say what actually happens.** If a Generator deletes objects it created earlier, write that, rather than that it "owns its output". The literal description is almost always shorter, and it tells the reader something they can act on.
- **Translate internal shorthand into what the reader experiences.** Specs and code use terms that are useful internally but are not product language. If a source says "combined pass", write what it does: "Infrahub recomputes affected values together rather than creating a separate job for every changed node." Established product terms stay exact; implementation shorthand gets translated.
- **Use Infrahub's own words**, consistently. [product-terminology](product-terminology.md) has which terms are capitalised, which stay lowercase, and the few where a generic synonym changes the meaning.
- **Name real cases.** Which situations to name, and how specific they have to be for a reader to tell whether they are in one, is [right-altitude](right-altitude.md)'s rule; it has the worked pairs.
- **Keep the technical terms.** Industry and protocol terms are precision, not decoration. LDAP, TLS, CIDR, GraphQL and RFC 5424 all stay.

### The check

The goal is not to eliminate ordinary English. It is to make technical behavior unambiguous. Write
out the non-technical verbs and expressions in the draft — the verb walk in
[checking-prose](checking-prose.md), which says where the list goes and how to cite it — and ask of
each one:

- Is a metaphor carrying technical meaning? "As it stood", "lives in", "owns its output", "drives"
  — each one was hiding something a reader needed stated.
- Could a reader take the phrase literally and misunderstand what the product does?
- Is there a more direct product or domain term available?
- Does the sentence still read naturally after the fix?

Figurative usage is open-ended, so no word list catches it — which is why the list is of the verbs
you wrote, not of verbs someone thought to ban. But do not trade a natural sentence for a stilted
one to satisfy this: if the meaning is unambiguous and the sentence reads well, leave it.

**House word choices**, already settled: **choose** not *pick*; **several** not *many* when the count is modest and countable; **manually** not *by hand*.

---

## Marketing register

Documentation and marketing describe the same product with different jobs. These are the ways marketing phrasing gets into docs.

**Do not imitate** vendor product pages (even when labelled "docs"), encyclopedia intros of the form "X is a Y that does Z", or enterprise software docs that are verbose, third-person, and full of implementation detail before purpose.

**The test that catches phrasings no list contains:** if the sentence would be equally true of any release of any product, it is a marketing claim. If it names something a reader could verify in their own instance, it is a consequence.

| Marketing claim | Consequence |
|---|---|
| "Teams move faster and stay productive." | "When you create a branch, Infrahub records a `branched_from` timestamp rather than copying the dataset." |
| "A more reliable, enterprise-grade platform." | "When you delete a branch, Infrahub removes the data recorded on that branch and leaves the default branch untouched." |

The right-hand column is a product claim and gets verified like any other. A fabricated specific is
worse than the vague claim it replaced, because it reads as though someone checked.

**When a sentence claims a benefit, say what the reader can now do.** Ask: what can this engineer
or team actually do that they could not before? If the answer can replace the claim, use it.

| Benefit claim | What they can do |
|---|---|
| "This gives teams greater visibility into historical infrastructure state." | "Compare the topology during an incident with the current topology." |
| "This improves change visibility." | "Identify which interfaces, relationships, or generated configurations changed after the update." |
| "This enables safer automation." | "Run the validation on every Proposed Change before the branch is merged." |

---

## Openers, links, and titles

### Openers

[right-altitude](right-altitude.md) owns openers in full: the shapes that work, the "use" rule, the
check, and how specific a named situation has to be.

### Put links inside sentences that say what is on the other side

A bare pointer makes the reader open the link to find out whether they needed it:

> ❌ "Refer to the object template guides."
> ✅ "To give a fleet of objects the same starting set of components, define them once in an [object template](https://docs.infrahub.app/object-templates/overview) and reuse it."

The reader who does not need it keeps reading, and has still learned what object templates are for. A `## Related` list at the end of a page is a useful complement, but it does not replace links inside the text, and its entries need descriptions too — a bare list of titles makes the reader open all of them.

### Page titles

Imperative for tasks, noun phrase for reference and concept pages. The test: would the page answer "How do I X?" If so the title is "X", not "X-ing".

| Page kind | Form | Example |
|---|---|---|
| How-to, guides, get started | Imperative | "Create a sync project", "Migrate from NetBox" |
| Reference | Noun phrase | "CLI reference", "Schema mapping reference" |
| Concept | Noun phrase | "NetBox adapter", "Branches and change control" |
| Sidebar section labels | Noun phrase | "Get started", "Adapters", "Reference" |

---

## Other rules

- No "Let me walk you through…" or "Let's get started…" — start the work.
- No apologies, compliments, or filler: "Great!", "Now you've successfully…".
- Write the sentence without a difficulty judgment. `Infrahub.simple-easy` catches `easy`, `simple` and `simply`; `easily` and `just` are not in that rule and have to be spotted by eye.
- No empty qualifiers: "canonical", "proper", "correct", "the right way". They imply an authoritative version exists when only one way is being described — "the canonical workflow for creating a Generator" is just "how to create a Generator". Keep a qualifier only when it adds information, such as "recommended" where a known alternative is being retired.
- Present tense. Active constructions where they make causality clearer. Second person for the
  reader's actions and choices; Infrahub, the feature, or the technical concept where that is the
  clearer subject — see [actors-and-causality](actors-and-causality.md).
- Rewrite bad phrasing when you move content rather than carrying it forward. "This guide" and "this tutorial" are fine to keep on a guide or a tutorial.
- Academy tutorials state the framing and the outcomes once — see [tutorial-extraction](../03-patterns/tutorial-extraction.md) for the convention and the precedent pages.

## The recurring failure modes

The list of what goes wrong most often, each entry paired with the fix on real text, is its own file:
[failure-modes](failure-modes.md). The drafting self-review and the pre-PR audit both check against
it.

## Match the section you are writing in

Before writing, read the existing pages closest to what you are about to write and match their sentence shape. [overview-page-content](../03-patterns/overview-page-content.md) has a table pairing the kind of page with the best existing example of it.
