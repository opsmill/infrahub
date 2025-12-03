# ADR-0003: Version Control and Temporal Graph

## Status

Draft

## Context

Infrahub needs to support Git-like branching and versioning of infrastructure data. Users must be able to work on changes in isolation, merge branches, and query historical states. The system must track when relationships and attributes were created, modified, or deleted.

## Decision

We implement a temporal, multi-dimensional graph where edges carry temporal properties (from/to timestamps) and branch information. Each branch maintains its own view of the graph, with merge operations combining changes. The global branch represents the merged state across all branches.

## Consequences

### Positive

- Git-like workflow familiar to developers
- Parallel development on multiple branches
- Historical queries via temporal properties
- Branch isolation prevents conflicts during development
- Supports proposed changes and review workflows

### Negative

- Complex merge logic required
- Increased storage for branch-specific data
- Query complexity increases with branch awareness
- Migration needed when graph schema changes

## Notes

- Branches are stored as nodes with metadata
- Edges have branch, branch_level, status, from, and to properties
- Merge operations use diff algorithms to combine changes
- Schema changes trigger branch migrations
- Global branch provides unified view across all branches
