---
paths:
  - "backend/infrahub/**/*.py"
---

# Backend Component Design (SOLID / DI)

Applies when creating a new backend component or making significant changes to an existing one. Does not apply to small bug fixes, single-function tweaks, or changes confined to existing code paths. When in doubt for anything that introduces a new class or reshapes responsibilities, follow this rule.

## Use modular components with dependency injection

New logic should live in components that receive their collaborators through constructor injection rather than instantiating them internally. This keeps components composable, swappable, and testable without patching.

## Build components near the application entry point

Construct components as close to the application entry point as possible. Use a builder class or factory function when wiring is non-trivial, and inject each sub-component rather than constructing it inside a parent component's `__init__`.

## Single entry point, operating on arguments

A component should generally expose a single entry point method (occasionally more, when justified by cohesive responsibility). That method only accepts the entities being operated on as arguments — it should not require additional dependencies to be passed in alongside the work payload.

## Constructor vs. method arguments

- `db` is always injected to the constructor.
- `branch` is usually injected to the constructor, but not always — inject it when the component's lifetime is tied to a single branch; pass it per-call when the component is reused across branches.
- Entities being examined or updated (nodes, schemas, diffs, request payloads) are passed to the entry method, not stored on the instance.

The boundary is: long-lived collaborators go in the constructor; transient work items go in the method.

## Single Responsibility Principle

Each component should have one reason to change. If a class is doing two unrelated things, split it. Prefer composition of small components over large multi-purpose ones.

## Interfaces for multiple implementations

When more than one implementation of a component is required (e.g. real vs. in-memory adapter, different backends, A/B variants), define a `Protocol` or abstract base class. The correct implementation is selected at the wiring layer and injected to the constructor — the consumer codes against the interface, not a concrete class.

A single implementation does not need an interface yet; introduce one when the second implementation arrives. Note that the second implementation
can be either a no-op version (such as in the case of an enterprise-only feature) or a testing version of a component (such as in the case of an
in-memory version of a component typically backed by the database).

## Why this matters

Constructor-injected long-lived dependencies plus method-passed transient entities is the boundary that lets components be reused across requests/operations and mocked with adapter implementations instead of `unittest.mock`. The [testing rule](./testing-python.md) requires adapter/protocol patterns for tests — that requirement is only practical when production code follows this design.

## Existing code

If existing nearby code violates this pattern, do not refactor it as part of an unrelated change. Raise it as a separate discussion — drive-by refactors balloon scope and make reviews harder.
