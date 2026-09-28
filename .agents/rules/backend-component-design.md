---
paths:
  - "backend/infrahub/**/*.py"
  - "python_testcontainers/infrahub_testcontainers/**/*.py"
---

# Backend Component Design (SOLID / DI)

Applies when creating a new backend component or making significant changes to an existing one. Does not apply to small bug fixes, single-function tweaks, or changes confined to existing code paths. When in doubt for anything that introduces a new class or reshapes responsibilities, follow this rule.

- Collaborators arrive through `__init__` as required parameters: no optional collaborator with an internal default, no late `set_*`/`register_*` call or attribute assignment, and a required `list[...]` when there can be zero or more.
- Build the whole component graph near the entry point, in one pass, before the work starts; a Prefect `@flow` resolves singleton getters at its top, builds the component and delegates to it.
- Resolve settings and out-of-domain clients in the factory, never inside the component, which takes plain values; invalid wiring raises while the graph is built.
- Expose a single entry method that takes only the entities being operated on: long-lived collaborators such as `db` go in the constructor, transient work items in the method.
- Give each component one reason to change, and make a reused component's `initialize()`/`reset()` clear everything derived from the previous input.
- Put new persistence behind a `Repository` that takes `db` and `Query` classes that return a `*QueryResult`; a model gets no persistence methods.
- A lookup into another component's data is a method on the component that owns it.
- Declare a `Protocol` or ABC when a second implementation arrives, or with one implementation to keep an out-of-domain dependency out of the logic's import chain.
- Dispatch across an open set of implementations through a `supports()` predicate and an injected list, not `isinstance` branching; a closed set takes an exhaustive `match`.
- A component that is hard to test without a mock needs splitting or its dependencies injected, since tests use adapters (`dev/guidelines/backend/testing.md`).
- Leave nearby code that violates this alone in an unrelated change, and raise it separately.

Full reference: `dev/guidelines/backend/component-design.md`
