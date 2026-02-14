# Documentation Architecture

This document explains how documentation is organized in the Infrahub project to ensure consistency and discoverability.

## Principles

1. **Single Source of Truth**: All technical knowledge lives under `dev/`
2. **AGENTS.md as Gateway**: Component-level `AGENTS.md` files provide quick reference and point to `dev/` for details
3. **No Cross-References in Guidelines**: Individual guideline files don't link to each other; they link back to their index (README.md)
4. **Index-Based Navigation**: Each guideline category has a README.md that serves as the index and navigation hub

## File Structure

```
infrahub/
├── AGENTS.md                    # Root entry point, points to component AGENTS and dev/
├── backend/
│   └── AGENTS.md               # Backend overview, points to dev/guidelines/backend/
├── frontend/app/
│   └── AGENTS.md               # Frontend overview, points to dev/guidelines/frontend/
└── dev/
    ├── guidelines/              # How to write code
    │   ├── backend/
    │   │   └── python.md
    │   └── frontend/
    │       ├── README.md       # Index: lists all frontend guidelines
    │       ├── typescript.md   # Points back to README.md, not to other guidelines
    │       └── url-construction.md  # Points back to README.md, not to other guidelines
    ├── knowledge/               # How the system works
    ├── guides/                  # How to do specific tasks
    ├── adr/                     # Architecture decision records
    └── specs/                   # Feature specifications
```

## Documentation Flow

### For Agents/Developers Reading Documentation

1. **Start at component level**: `backend/AGENTS.md` or `frontend/app/AGENTS.md`
2. **Navigate to guidelines**: Follow link to `dev/guidelines/[backend|frontend]/`
3. **Use the index**: Start at `README.md` to see all available guidelines
4. **Read specific guidelines**: Each guideline is self-contained and focused

### For Agents/Developers Writing Documentation

#### ✅ DO

- Put all technical knowledge in `dev/` directories
- Create a README.md index file for guideline categories
- Link from component AGENTS.md to `dev/guidelines/[category]/README.md`
- Link from individual guidelines back to their README.md index
- Keep guidelines focused and self-contained

#### ❌ DON'T

- Put detailed coding standards in component AGENTS.md files
- Cross-reference between individual guideline files (use the index instead)
- Duplicate content between AGENTS.md and dev/ files
- Create guideline files without adding them to the README.md index

## Example: Frontend Guidelines

```markdown
# frontend/app/AGENTS.md
- Points to: dev/guidelines/frontend/README.md

# dev/guidelines/frontend/README.md (Index)
- Lists: typescript.md, url-construction.md
- Points to: related knowledge, guides, other dev/ files

# dev/guidelines/frontend/typescript.md
- Header links back to: README.md
- Does NOT link to: url-construction.md (use index instead)

# dev/guidelines/frontend/url-construction.md
- Header links back to: README.md
- Does NOT link to: typescript.md (use index instead)
```

## Why This Pattern?

### Benefits

1. **Discoverability**: The README.md index provides a complete view of all guidelines in a category
2. **Maintainability**: Changes to one guideline don't require updating cross-references in other files
3. **Scalability**: Easy to add new guidelines - just add to the index
4. **Clear Hierarchy**: Component AGENTS.md → Guidelines Index → Specific Guideline
5. **Context for AI Agents**: All related guidelines are discoverable through the index, ensuring agents have complete context

### Comparison to Backend Pattern

The backend currently uses direct cross-references (e.g., `python.md` → `architecture.md`). While this works for a small number of files, the frontend pattern scales better:

- **Backend**: Works well with 1-2 guideline files
- **Frontend**: Scales to many guideline files without creating a cross-reference web

Both patterns are acceptable, but prefer the **index-based pattern** (frontend style) for categories with 3+ guideline files.

## Updating the Pattern

When adding new guidelines:

1. Create the guideline file in the appropriate `dev/guidelines/[category]/` directory
2. Add header: `> Part of: dev/guidelines/[category]/ | Index: [Category Guidelines](./README.md)`
3. Update the category's README.md index with the new guideline
4. If this is the first guideline beyond the initial one, consider creating a README.md index

## Summary

- **Component AGENTS.md**: Quick reference → Points to `dev/`
- **dev/guidelines/[category]/README.md**: Index → Lists all guidelines in category
- **dev/guidelines/[category]/[specific].md**: Focused guideline → Points back to README.md index
- **Result**: Clear hierarchy, easy navigation, scales well, complete context for agents
