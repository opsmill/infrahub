# Writing Documentation

> Part of: `dev/guidelines/` | Related: [Markdown Standards](markdown.md), `docs/AGENTS.md`

Guidelines for writing documentation in the Infrahub project. These principles apply to all documentation, regardless of format.

## Documentation Types

Infrahub documentation follows the [Diataxis framework](https://diataxis.fr/), separating documentation into four categories:

- **Tutorials** - Learning-oriented walkthroughs (complete learning scenarios)
- **Guides** - Task-oriented how-to documentation (steps to complete a task)
- **Topics** - Understanding-oriented explanations (how something works)
- **Reference** - Information-oriented specifications (API/command references)

### Choosing the Right Type

| Question | Doc Type | Location |
|----------|----------|----------|
| Walking through a complete learning scenario? | **Tutorial** | `docs/docs/tutorials/` |
| Teaching users to complete a specific task? | **Guide** | `docs/docs/guides/` |
| Explaining concepts or how something works? | **Topic** | `docs/docs/topics/` |
| Providing reference information? | **Reference** | `docs/docs/reference/` |

## Writing Style

### For Guides (How-to)

- **Direct and imperative**: Use commands that tell the user what to do
- **Task-focused**: Stay focused on the specific goal without digressing
- **Active voice**: "Create a branch" (not "A branch can be created")
- **Imperative mood**: "Click **New Branch**" (not "You should click New Branch")
- **Second person**: Address the user directly with "you"

### For Topics (Explanations)

- **Discursive and reflective**: Invite understanding through explanation
- **Contextual**: Provide background and rationale
- **Analytical**: Explore the "why" behind decisions
- **Present tense**: "Infrahub uses branches to isolate changes"
- **Third person acceptable**: "The schema defines the data model"

### For Internal Docs

Applies to `dev/`, the `AGENTS.md` files, and `.agents/`. These are read mid-task, by people and
agents with a job to finish.

- **Rule first**: open with the imperative, then the reason. One sentence of reason is usually enough
- **Plain words**: say what happens — "the transaction commits", not "the exit hook takes the success
  path". Name a symbol only when the reader has to go find it
- **Show instead of qualifying**: a ✅/❌ pair replaces a paragraph of caveats
- **No provenance**: where a rule came from — a review thread, a ticket, a PR, a spec, a line number —
  belongs in the commit message, not the doc. See the last two entries under
  [Don't](#dont) for what that rules out
- **No padding**: cut "note that", "it's important to", "keep in mind", bolded whole sentences, and any
  sentence that restates the one before it
- **Say it once**: if the rule is already written elsewhere, link to it instead of restating it
- **Budget**: a new rule is a few lines plus one example. If it needs more than that, it's an
  explanation for `dev/knowledge/`, not a guideline
- **Relative numbers, not absolute ones**: a measurement is only meaningful as a comparison, since the
  absolute figure depends on the environment it was taken in. Write "cuts merge wall time by roughly
  4x", not "runs in 10s"
- **Pay for it**: cut the prose the new rule supersedes, and check the file against its size range
  in [Repository Organization](repository-organization.md) before appending. A file over its range
  gets split or compressed, not extended

## Content Guidelines

### Do

**For Guides:**

- Use conditional imperatives: "If you want X, do Y"
- Focus on actions, not explanations
- Provide multiple methods when applicable (UI, GraphQL, CLI)
- Include verification steps after each major action
- Use clear titles that state exactly what will be accomplished (2-5 words)
- Add screenshots for UI-based tasks
- Break complex workflows into logical sections
- Provide troubleshooting tips for common issues

**For Topics:**

- Explain the reasoning behind design decisions
- Provide context and background information
- Use analogies to connect to familiar concepts
- Explore different perspectives and approaches
- Include diagrams and visual aids for complex concepts
- Make connections to related topics
- Answer "why" questions explicitly
- Discuss trade-offs and alternatives
- Use consistent terminology throughout

**For All Documentation:**

- Include code examples with proper syntax highlighting
- Link to topic/explanation docs for background information (in guides)
- Link to guides for task instructions (in topics)
- Define technical terms on first use
- Before citing a specific test as verifying a scenario (a spec table, a status doc), confirm that test function actually exists in the change or repo — label not-yet-written coverage as planned/unverified instead of naming a test that isn't there

### Don't

- Explain concepts in detail in guides (link to topics instead)
- Provide step-by-step instructions in topics (use guides instead)
- Use words like "easy", "simple", or "just"
- Digress into background information in guides
- Skip verification steps (in guides)
- Assume steps are self-explanatory (in guides)
- Mix guide and topic content in the same document
- Use vague or generic titles
- Assume prior knowledge of Infrahub-specific concepts (in topics)
- Use marketing language or hype (in topics)
- Skip definitions of technical terms
- Focus on "how to" instead of "how it works" (in topics)
<<<<<<< HEAD
- Reference Jira tickets, GitHub issues, or spec IDs — describe the behavior or constraint itself;
  work-item IDs belong in commit messages, PR descriptions, and changelog fragments
=======
- Reference Jira tickets, GitHub issues, PR numbers, or spec files as the reason for a rule — describe the underlying behavior or constraint instead. These rot once the item closes and the spec is forgotten, and a reader can't verify a closed reference the way a reviewer could at review time. Work-item IDs belong in commit messages, PR descriptions, and changelog fragments; track a significant architectural decision in `dev/adr/` (see `dev/adr/README.md`) instead, written as a self-contained Context/Decision/Consequences record independent of the spec that prompted it
- Cite a `file.py:123` or `file.py:100-140` line location — reference the module path and symbol only (`some/module.py::SomeClass`). A symbol reference survives the code moving within a file or being renamed at the call site; a line number does not, and a spec's own line-numbered citations routinely rot before the feature it describes even merges
>>>>>>> origin/stable

## Documentation Workflow

1. **Choose documentation type** using the table above
2. **Follow specialized guide**:
   - Guides: [Writing a Guide](../guides/docs/writing-a-guide.md)
   - Topics: [Writing a Topic](../guides/docs/writing-a-topic.md)
3. **Create the .mdx file** in the appropriate directory
4. **Add to navigation** by editing `sidebars.ts` in the appropriate section
5. **Lint before committing**: `uv run invoke docs.lint`
6. **Build to verify**: `uv run invoke docs.build`
7. **Serve for human verification**: `uv run invoke docs.serve`

## Commands

```bash
# Linting & Validation
uv run invoke docs.lint          # Run all linters (Vale + markdownlint)

# Development
uv run invoke docs.build         # Build documentation site
uv run invoke docs.serve         # Serve documentation site

# Format
uv run invoke docs.format        # Auto-format markdown files
```

## See Also

- [Markdown Standards](markdown.md) - Markdown formatting standards
- [Writing a Guide](../guides/docs/writing-a-guide.md) - Step-by-step guide for writing guides
- [Writing a Topic](../guides/docs/writing-a-topic.md) - Step-by-step guide for writing topics
- `docs/AGENTS.md` - Main documentation guidelines
- [Diataxis Framework](https://diataxis.fr/) - Documentation framework
