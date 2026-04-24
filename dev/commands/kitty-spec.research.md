---
description: Run Phase 0 research scaffolding before planning to resolve unknowns and make informed technology decisions.
handoffs:
  - label: Build Technical Plan
    agent: kitty-spec.plan
    prompt: Create a plan based on the research findings
    send: true
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

This command extracts and formalizes the research phase into a standalone step, producing a structured `research.md` before planning begins.

1. **Setup**: Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root and parse JSON for FEATURE_DIR and AVAILABLE_DOCS. All paths must be absolute.

2. **Load context**:
   - Read `FEATURE_DIR/spec.md` for feature requirements and scope
   - Read `.specify/memory/constitution.md` for project principles and constraints
   - If `FEATURE_DIR/plan.md` exists, scan for NEEDS CLARIFICATION markers

3. **Identify research areas**: For each area needing investigation:
   - Technology choices referenced in spec or plan
   - Integration patterns with existing systems
   - Security or compliance requirements
   - Performance or scalability concerns
   - Third-party dependencies or APIs
   - Domain-specific best practices

4. **Conduct research**: For each identified area:
   - Research best practices, patterns, and alternatives
   - Use web search if available for up-to-date information
   - Evaluate trade-offs (complexity, maintenance, performance, team familiarity)
   - Consider project constitution principles when making recommendations

5. **Consolidate findings** into `FEATURE_DIR/research.md`:

   ```markdown
   # Research: [Feature Name]

   ## Summary

   <high-level overview of research conducted and key decisions>

   ## Decisions

   ### [Topic 1]

   - **Decision**: [what was chosen]
   - **Rationale**: [why this option was selected]
   - **Alternatives considered**:
     - [Alternative A]: [why rejected]
     - [Alternative B]: [why rejected]
   - **Risks**: [known risks or trade-offs]

   ### [Topic 2]
   ...

   ## Open Questions

   <any remaining questions that need stakeholder input>

   ## References

   <links to documentation, articles, or resources consulted>
   ```

6. **Optionally populate** `FEATURE_DIR/data-model.md` with initial entity sketches if the research reveals clear data structures.

7. **Report**:
   - Path to `research.md`
   - Decisions made (count and summary)
   - Areas still needing clarification (if any)
   - Suggest running `/kitty-spec.plan` next to build the technical plan

## Guidelines

- Focus on decisions that affect architecture, not implementation details
- Prefer options that align with project constitution principles
- Document trade-offs explicitly -- don't just pick the "best" option without explaining why alternatives were rejected
- Keep research actionable: every section should inform a planning or implementation decision
- If web search is unavailable, rely on codebase context, existing patterns, and general best practices
