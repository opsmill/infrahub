# Step 3 — Outline and pattern decision ★ (when no recommendations doc exists)

When no outline exists, this step produces one. Recommend a pattern based on the Step 2 audit and the user's inputs, then build the full outline for user approval before drafting.

**This step always runs, and its size scales.** For a small change the outline is a few lines; for a
rework it is a section-by-section plan. What never gets skipped is the gate, because this is where
the scope is agreed.

## Phase 1 must be complete before you outline

The outline is where research turns into a plan, so it is built from all of it: the existing pages you read at [Step 2](step-2-audit.md), the spec review at [Step 2.5](step-2.5-spec-review.md), and the comparable-docs review and gap list at [Step 2.7](step-2.7-content-audit.md). If any of those hasn't happened, go back and do it — outlining first and researching later means restructuring a written page, which costs several rounds instead of one message.

State in the outline what the research changed. "Kubernetes gives each option identical subsections so they can be compared, so the outline gives each method the same three beats" is the kind of line that lets the user check the reasoning rather than only the result.

## Propose the scope, not a plan

The audit at [Step 2](step-2-audit.md) produced a list of what is weak on the page. Turn that list
into choices:

- **The change that was asked for** — what it fixes, and roughly how many lines.
- **The fuller rework** — what else it fixes, and roughly how many lines.
- **Your recommendation, with the reason.** Not a preference, a reason. "The new opening would
  otherwise sit directly on top of the vaguest paragraph on the page" is a reason.

The user chooses. Draft nothing until they have.

If the audit found nothing beyond the requested change, say so in one line and carry on. Adding an
attribute to a documented feature should not trigger a scoping conversation.

Name whatever the chosen scope leaves out, here and again in the pull request, so the user is the
one deciding what to leave and can see the list while deciding.

## Show the content, not the work

An outline that says "new section on when to use this" cannot be reviewed. The reviewer has to wait
for the drafted page, and by then changing direction costs several rounds of rewriting.

- **Every line is something the page will state.** "Four kinds of value worth computing" tells the
  reviewer nothing. The four actual kinds tells them everything.
- **Attach the source to each claim** — a code path with a line number, the existing page, a blog, a
  brief. The reviewer can then see which claims are verified and which are your reasoning.
- **Flag anything you are unsure of, in the outline itself.** That is the last cheap moment for
  someone to say "no, that isn't what a display label is for".

### Updating an existing page: before and after

Lead with a short decision — what is weak, the options, your recommendation and why, and anything
you need an answer on. Then one row per section:

| Section | Today | After |
|---|---|---|
| Opening | "The computed attributes feature enables the dynamic calculation of attribute values based on user-defined logic." | "A computed attribute is a read-only `Text` or `URL` value calculated from data already modeled in Infrahub. Use it where the value should stay in step with the attributes and relationships it is built from." |
| Jinja2 versus Python | "Lightweight" versus "More flexible and powerful" | Four rows on what actually decides it: what each can calculate, relationship support, whether the attribute can be mandatory, when the calculation runs. |
| Which derived value do you want | *doesn't exist* | Display label, human-friendly ID, or computed attribute, and when each is right. ⚠️ unsure about the display label line — check before drafting |

Sources go at the bottom as numbered notes. The comparison does the explaining: a reviewer sees that
"lightweight versus powerful" is being replaced by four rows about relationship cardinality, and can
judge that in seconds.

### A brand new page: the decision page

There is no "today" column to compare against, so lead with the same short decision, then go section
by section — the heading, one line on why the section exists, then the facts it will state, each with
its source and its flags.

## Read the navigation map first

For Infrahub main repo work, **read [docs-navigation-map](../04-infrahub/docs-navigation-map.md) before drafting the outline.** That file decides:

- **Which top-level section** the content belongs in (Get started / Learn / Schema & Data / Branches & Change Control / Design & Integrate / Deployment & Management / Development Resources / Reference / Project)
- **Which sub-section** within that section
- **Which Diátaxis quadrant** (concept / how-to / tutorial / reference) and therefore which file path inside the section
- **Whether content needs to land in a satellite repo** (Sync, SDK, Ansible, Nornir, infrahubctl, MCP) instead of, or in addition to, main Infrahub

For other repos, the navigation map doesn't apply — the user provides placement at Step 0.5.

## The outline should cover

- Where the docs live — section and sub-section per the [navigation map](../04-infrahub/docs-navigation-map.md), file paths under `docs/docs/<section>/`, and the sidebar entry shape.
- The pattern — single-page-merge, hub + spokes, or tutorial extraction (see [decision rules](../03-patterns/decision-rules.md)).
- The shape of each page — what the introducing page opens with, which is [right-altitude](../01-principles/right-altitude.md)'s call (a definition, a capability or a situation, never the word "use"), and for each how-to whether the order of its steps is a dependency, the only case for numbered steps ([steps-vs-sections](../01-principles/steps-vs-sections.md)).
- For hub + spokes: each spoke's name and a one- or two-sentence summary of what it covers (overview material, how-to content, best practices, examples).
- **The introducing page's content, section by section, against the [overview page content model](../03-patterns/overview-page-content.md).** Outline the five parts explicitly — capability lead, the situation that makes the feature relevant, the concepts needed to decide, the paths with what distinguishes each, and where to go next. Two of these are where outlines go wrong, so make them visible at the gate rather than deferring them to drafting:
  - **The "why you would use it" section** — say in the outline what that paragraph will assert, and where it comes from. Where a source establishes it, cite the source. Where no source does, reason from what you have and write the claim anyway, labelled as a recommendation for the user or the feature owner to confirm ([Step 2.7](step-2.7-content-audit.md)). What is not acceptable is deferring it: "I'll write something once I'm drafting" means the page's why-layer never gets agreed, and drafting invents it unreviewed.
  - **The paths** — list them with the distinguishing sentence for each. If the paths can't be told apart at outline stage, the page won't help anyone choose, and the fix is content, not layout.
- **Any adjacent Infrahub mechanism the reader has to choose between** and where the page settles it
  ([Step 2.7](step-2.7-content-audit.md), [hub-and-spoke-scope](../03-patterns/hub-and-spoke-scope.md)).
- Any Academy tutorials and their scenario shape.
- **Cross-repo placement** — if any content also belongs in a satellite repo, list what goes where and call out that each repo gets its own PR.
- Rationale — why this structure, with reference to the decision rules and the source inputs.
- **Mapping back to source inputs, with links** — messaging brief sections, JPD requirements, spec-kit tasks, transcripts, related existing docs. Link each one: a repo-relative file path, a URL, or a Notion link, named down to the section where the material actually is rather than to the document as a whole.

  The links are what makes the mapping usable. [Step 4](step-4-create-files.md) re-opens the sources for each section before writing it, so a mapping that names a document without saying where to find it sends drafting back to searching, or to working from the outline's summary instead — which is the failure the mapping exists to prevent.

  **These links are why the outline file stays uncommitted.** They point at transcripts, JPD cards, KB entries and Notion pages, which are internal and often name a customer. That is fine in a local working file and not fine in a public repository ([no-customer-pii](../01-principles/no-customer-pii.md)). If the user asks for the outline to be committed, generalize the mapping first: keep the fact each section rests on, drop the link that identifies whose it was.

## Where to deliver the outline

For a worked example of what an outline looks like, see the IPAM docs recommendation page (it was produced as an outline in this format and used as the input for drafting).

**Write the outline to a file** — `dev/specs/docs/<slug>.md` in Infrahub main, creating the directory if it does not exist. Leave it uncommitted unless the user asks for it, and generalize the source mapping first if they do (see the note above). Publish to Notion as well when other people review it before drafting starts. Chat gets a summary of the decisions and the gate questions, not the outline itself; see "Drafts live in files" in SKILL.md.

Keeping it in a file matters beyond tidiness. Step 4 drafts each section against the outline's source mapping, and both need to be re-read section by section while writing — which is only possible if the outline still exists somewhere. An outline that lived only in a chat message is gone by the time it is needed, and drafting then runs on a memory of it.

## Apply the tutorial scenario-shape test

If the chosen pattern preserves an Academy tutorial (Tutorial extraction or Split), run the [tutorial scenario-shape test](../01-principles/tutorial-shape-test.md) before committing to the pattern. Do not ship feature-oriented tutorials.

★ **Gate**: present the outline. **Surface each major decision separately as a named item**, not as a single "looks good?" blob. The user approves (or pushes back on) each one independently:

0. **Scope** — the options above, with your recommendation and the reason. On a page that already exists this is the first thing the user should see, because it decides what the rest of the gate is even about.
1. **Placement** — top-level section + sub-section + Diátaxis quadrant + cross-repo split (if any). For each, cite the [navigation map](../04-infrahub/docs-navigation-map.md) line that justifies it ("Per the map, IPAM lives under Schema & Data > IPAM as a hub+spokes feature").

   **When placement is ambiguous** — the feature is new, nothing like it exists in the current docs, or the navigation map doesn't clearly cover it — **do not ask the user to decide cold.** Instead, research how comparable OSS tools document the same or similar capability. Name the tools you checked and where they placed it. Then make a recommendation with rationale. The user evaluates a reasoned recommendation; they cannot easily answer "what section does this belong in?" for a feature they may be seeing for the first time.

   This is the default path for net-new features that exist in some form elsewhere (graph traversal, IP address management, role-based access control, dependency mapping, etc.). Competitor placement research is preferable to an open-ended question.

2. **Pattern** — single-page-merge / hub+spokes / tutorial extraction / split, with rationale per the [decision rules](../03-patterns/decision-rules.md).
3. **Spoke breakdown** — for hub+spokes, the spoke names and one-sentence summaries.
4. **The why-layer** — the claim the "why you would use it" paragraph will make, and whether it is sourced or reasoned. Approving it here is what makes it writable at Step 4 without asking again; approving a structure is not approval of a claim nobody stated. Present sourced and reasoned claims differently, so the user knows which ones they are being asked to vouch for.
5. **Tutorial scenario-shape verdict** — if applicable.
6. **Pull request scope** — propose one pull request covering the whole outline, and give the user the chance to say otherwise ([Step 1](step-1-preflight.md)). If something found during research is deliberately being left for later, list it here so it is agreed rather than assumed.

Why separate items: placement decisions get rubber-stamped when bundled with structural ones. Forcing the user to approve placement on its own makes mis-placement explicit instead of inferred. Mis-placement is much cheaper to fix here than after Step 4 drafting.
