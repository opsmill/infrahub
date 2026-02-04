# Backend Development Checklist

> Part of: `dev/guidelines/backend/` | Related: [Python Standards](./python.md), [Testing Standards](./testing.md)

Key questions to consider when planning and implementing new backend features. Use this checklist during feature planning, design discussions, and implementation to ensure all critical aspects are addressed.

## Database & Schema

### Will this feature require a database migration?

Consider whether the feature will:

- Add, remove, or modify node/relationship properties in ways that the schema migrations can't resolve
- Change indexes or constraints
- Alter the graph structure or schema definitions
- Modify how data is stored in Neo4j

Plan to create a migration in `backend/infrahub/core/migrations/graph/` if any of these apply.

### How will this feature maintain graph integrity?

Design the feature to ensure:

- **Constraints are validated** before writing to the database
- **Relationship cardinality** is enforced (e.g., required relationships exist)
- **Unique constraints** are respected
- **Data consistency** is maintained across branches

## Performance & Scalability

### How many database queries will this feature require at different scales?

Plan for query efficiency and data volume by considering:

- **Database round-trips** - design to use batch queries when operating on multiple nodes
- **N+1 query patterns** - plan to load related data in bulk rather than iteratively
- **Data volume per query** - avoid overquerying by fetching only necessary fields and relationships
- **Memory footprint** - consider how much data will be held in memory during processing
- **Pagination and streaming** - plan to process large result sets incrementally when appropriate
- **Scalability testing** - consider how the feature behaves with 10, 100, 1000+ nodes
- **Query optimization** - plan to use EXPLAIN in Neo4j to validate query performance

## Security & Access Control

### What permissions will be needed to restrict access to this feature?

Plan the access control requirements:

- **Authentication requirements** - will this require a logged-in user?
- **Role-based access control** - should only certain roles have access?
- **Object-level permissions** - should users only access/modify their own resources?
- **Branch permissions** - are branch-specific restrictions needed?

## Error Handling & User Experience

### How will users be informed when the feature fails?

Plan error handling to include:

- **Meaningful exceptions** with clear error messages
- **Appropriate logging** - use structured logging for debugging
- **User-friendly messages** - avoid exposing internal implementation details
- **Actionable guidance** - help users understand how to resolve the issue

## Branching & Multi-Tenancy

### How will this feature behave with branch-agnostic nodes?

Branch-agnostic nodes exist across all branches. Plan for:

- **Cross-branch impact** - will changes affect all branches or only the current branch?
- **Branch-specific overrides** - should these be allowed or prevented?
- **Merge behavior** - how should merges handle branch-agnostic data?
- **UI indicators** - how will users understand branch-agnostic behavior?

## Documentation & SDK

### What documentation will this feature require?

Plan for documentation updates:

- **New features or APIs** - plan to document in `docs/`
- **Behavior changes** - identify existing docs that need updates
- **GraphQL schema changes** - plan to regenerate schema docs
- **Configuration options** - document in relevant guides

### Will this feature require SDK changes?

Consider SDK implications:

- **New API endpoints or custom GraphQL queries/mutations** - plan to expose in Python SDK
- **Request/response models** - identify SDK types that need updates
- **Authentication flow changes** - plan SDK auth updates
- **New mutations** - design SDK helper methods

The Python SDK is in `python_sdk/` (Git submodule).

## Testing & Code Quality

### How will this feature be tested?

Plan for comprehensive test coverage:

- **Unit tests** - plan to test individual functions/classes in isolation
- **Component tests** - plan database access tests for queries/repositories
- **Integration tests** - plan end-to-end flow tests with Neo4j
- **Edge cases** - plan tests for error conditions, empty data, large datasets
- **Branch scenarios** - plan tests for both default and feature branches

### How will naming align with existing code patterns?

Plan to follow established patterns:

- **Existing naming conventions** - review similar functions before implementing
- **Consistent verb patterns** - use `create_`, `update_`, `delete_`, `get_`, `list_`
- **Standard parameter names** - use `db`, `node_id`, `branch_name` consistently
- **Domain language** - choose names that match terminology from the domain model

## See Also

- [Python Coding Standards](./python.md) - Python coding conventions
- [Testing Standards](./testing.md) - Testing patterns and best practices
- [Backend Architecture](../../knowledge/backend/architecture.md) - Backend architecture overview
