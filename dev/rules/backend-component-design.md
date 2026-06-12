---
paths:
  - "backend/infrahub/**/*.py"
---

# Backend Component Design (SOLID / DI)

Applies when creating a new backend component or making significant changes to an existing one. Does not apply to small bug fixes, single-function tweaks, or changes confined to existing code paths. When in doubt for anything that introduces a new class or reshapes responsibilities, follow this rule.

## Use modular components with dependency injection

New logic should live in components that receive their collaborators through constructor injection rather than instantiating them internally. This keeps components composable, swappable, and testable without patching.

## Required dependencies, not optional

Constructor dependencies for new code are required parameters - not `collaborator: Collaborator | None = None` with an internal default. Optional injection hides that the dependency exists and lets a caller silently skip wiring it. Make every collaborator an explicit, required constructor argument - explicit is better than implicit.

The single exception is editing existing code where adding a required parameter would force a large change across many call sites. There, an optional parameter is a transitional compromise to keep the change small - not the target shape for new components.

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

## Dispatching across implementations

When a component must pick one of several implementations at runtime based on the input, do not branch with `isinstance` (or a `match` on the input's type) inside one class. Give each implementation a predicate on the shared interface (e.g. `supports(request) -> bool`) alongside its entry method, hold the implementations as an injected list in an aggregator component, and let the aggregator delegate to the first that supports the input:

```python
class CheckerInterface(ABC):
    @abstractmethod
    def supports(self, request: Request) -> bool: ...
    @abstractmethod
    def check(self, request: Request) -> Result: ...

class AggregatedChecker:
    def __init__(self, checkers: list[CheckerInterface]) -> None:
        self.checkers = checkers

    def run(self, request: Request) -> Result:
        for checker in self.checkers:
            if checker.supports(request):
                return checker.check(request)
        raise NoCheckerError(request)
```

The aggregator depends only on the interface; the concrete list is assembled by the factory at the wiring layer, so adding an implementation is one new class plus one line in the factory, with no edit to the dispatch logic. `AggregatedConstraintChecker` (`backend/infrahub/core/validators/`) is the canonical example in the codebase.

This is for an open, extensible set of implementations. When the set is closed and fixed (an enum, a sealed union), an exhaustive `match` with `typing.assert_never` is the right tool instead.

## Why this design matters

Stepping back from the individual rules above: constructor-injected long-lived dependencies plus method-passed transient entities is the boundary that lets components be reused across requests/operations and mocked with adapter implementations instead of `unittest.mock`. The [testing rule](./testing-python.md) requires adapter/protocol patterns for tests — that requirement is only practical when production code follows this design.

Use this as a design driver, not just a constraint: the no-mock rule is the forcing function for this structure. When you make a component's decision logic testable without patching — collaborators injected through the constructor, a single entry point that is pure and operates only on its arguments — dependency inversion and single responsibility fall out as the path of least resistance rather than discipline you have to summon. The corollary is a useful smell test: if a component is hard to test without a mock, that is the signal it needs splitting or its dependencies injected, not that it needs a mock.

## Existing code

If existing nearby code violates this pattern, do not refactor it as part of an unrelated change. Raise it as a separate discussion — drive-by refactors balloon scope and make reviews harder.
