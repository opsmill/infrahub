Create a new Architecture Decision Record (ADR) in the docs/adr/ directory.

The command expects one argument:
- ADR title (e.g., "use-redis-for-caching" - will be converted to title case)

Follow these steps:

1. List all existing ADR files in docs/adr/ directory
2. Extract the highest ADR number from existing files (e.g., if ADR-0008 exists, next number is 0009)
3. Auto-generate the next ADR number (increment the highest number by 1, pad to 4 digits)
4. Extract the title from $ARGUMENTS (convert kebab-case to Title Case for the heading)
5. Generate the filename: `ADR-XXXX-title-in-kebab-case.md` where XXXX is the auto-generated number
6. Check if the file already exists in docs/adr/ - if it does, ask the user before overwriting
7. Create the ADR file with the following template structure:

```markdown
# ADR-XXXX: [Title in Title Case]

## Status

Proposed

## Context

[Describe the context and problem statement that motivates this decision]

## Decision

[Describe the decision that was made]

## Consequences

### Positive

- [List positive consequences]

### Negative

- [List negative consequences]

## Notes

- [Add implementation notes and references]
```

8. Use the exact format from existing ADRs (see docs/adr/ADR-0001-async-first-architecture.md as reference)
9. Set Status to "Proposed" by default
10. Ensure the filename uses kebab-case for the title portion
11. Verify the file was created successfully and display the created filename

Example usage:
- `create-adr use-redis-for-caching` → Creates `ADR-0009-use-redis-for-caching.md` (if ADR-0008 is the highest existing)
- `create-adr dual-api-strategy` → Creates `ADR-0010-dual-api-strategy.md` (if ADR-0009 is the highest existing)

