# ADR-0004: Schema-Driven Architecture

## Status

Draft

## Context

Infrahub must support dynamic schema definitions that can be modified without code changes. Users define node types, attributes, and relationships through YAML schema files. The system needs to generate Python code, GraphQL types, and database structures from these schemas.

## Decision

We use a schema-driven architecture where YAML schema definitions are loaded, validated, and processed to generate Python classes, GraphQL schemas, and database structures. The schema registry maintains branch-specific schema versions, and code generation creates type-safe Python classes.

## Consequences

### Positive

- No code changes needed for schema modifications
- Type safety through generated code
- Consistent schema across GraphQL, REST, and database
- Branch-specific schema evolution
- Validation ensures schema consistency

### Negative

- Code generation adds build step complexity
- Generated files must not be manually edited
- Schema changes require regeneration
- Learning curve for schema definition format
- Debugging generated code can be challenging

## Notes

- Jinja2 templates generate Python code
- Schema registry caches processed schemas per branch
- Schema validation runs before code generation
- Generated files in backend/infrahub/core/schema/generated/

