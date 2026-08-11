---
paths:
  - "backend/infrahub/**/*.py"
  - "python_testcontainers/infrahub_testcontainers/**/*.py"
---

# Backend Component Design (SOLID / DI)

Applies when creating a new backend component or making significant changes to an existing one. Does not apply to small bug fixes, single-function tweaks, or changes confined to existing code paths. When in doubt for anything that introduces a new class or reshapes responsibilities, follow this rule.

## Use modular components with dependency injection

New logic should live in components that receive their collaborators through constructor injection rather than instantiating them internally. This keeps components composable, swappable, and testable without patching.

## Required dependencies, not optional

Constructor dependencies for new code are required parameters - not `collaborator: Collaborator | None = None` with an internal default. Optional injection hides that the dependency exists and lets a caller silently skip wiring it. Make every collaborator an explicit, required constructor argument - explicit is better than implicit.

The single exception is editing existing code where adding a required parameter would force a large change across many call sites. There, an optional parameter is a transitional compromise to keep the change small - not the target shape for new components.

Late registration is the same anti-pattern in another shape. `set_collaborator(x)`, `register_handler(fn)`, or assigning `obj.on_change = fn` after construction hides the dependency at construction, lets a caller skip wiring it, lets a second caller silently clobber the first's, and forces a `None` check at every use site. Pass it to `__init__`. When the component feeds zero or more collaborators rather than exactly one, that argument is a required `list[...]`, and callers with nothing to wire pass `[]` explicitly.

## Build components near the application entry point

Construct components as close to the application entry point as possible. Use a builder class or factory function when wiring is non-trivial, and inject each sub-component rather than constructing it inside a parent component's `__init__`.

Prefect `@flow` functions are application entry points: resolve singleton getters (`get_database()`, `get_workflow()`, …) at the top of the flow only — never inside helpers or component internals — then build the component and delegate to it. The flow body stays a thin composition root; the business logic lives in the component.

Anything that comes from outside the component's own domain — loaded settings, an external service client, a telemetry sink — is resolved at that entry point, never inside the component:

- **Settings resolve in the factory, not the component.** A component takes plain values (`window_seconds: float`, `max_retries: int`), never a `Settings` object and never a module-global read. The factory is then the only place that knows a value came from configuration, which is also what makes the component directly testable with hand-picked values.
- **The factory takes its out-of-domain collaborators as parameters too**, rather than choosing them. A factory that both reads settings *and* picks the concrete adapters has only moved the coupling one level out; take them as arguments so the entry point names them and the factory stays reusable with different ones.
- **Configure at construction, never by assignment afterwards.** Reaching into a built object to finish setting it up leaves a window in which it is misconfigured, makes a fixed value look mutable, and scatters the wiring across two places. Pass it to `__init__`, and expose it through a read-only property if callers need to read it back.
- **A lazily-built process-global lives in its own registry module**, separate from the component it builds, so importing the component never drags the wiring — and the dependencies behind it — into the import chain. Build on first use rather than at import, so the settings read happens after configuration is loaded and importing the module stays free of side effects.

## Single entry point, operating on arguments

A component should generally expose a single entry point method (occasionally more, when justified by cohesive responsibility). That method only accepts the entities being operated on as arguments — it should not require additional dependencies to be passed in alongside the work payload.

## Constructor vs. method arguments

- `db` is always injected to the constructor.
- `branch` is usually injected to the constructor, but not always — inject it when the component's lifetime is tied to a single branch; pass it per-call when the component is reused across branches.
- Entities being examined or updated (nodes, schemas, diffs, request payloads) are passed to the entry method, not stored on the instance.

The boundary is: long-lived collaborators go in the constructor; transient work items go in the method.

## Single Responsibility Principle

Each component should have one reason to change. If a class is doing two unrelated things, split it. Prefer composition of small components over large multi-purpose ones.

## Persistence lives in Repository/Query classes, not on models

For new code, database access and (de)serialization do not belong on the model. A model is a plain data holder; give it no `save`/`get`/`get_list`/`from_db`/`to_db` methods. Instead:

- Put read/write access behind a `Repository` class that takes `db` in its constructor and exposes intent-named methods (`get_for_owner`, `get_all`, `save`).
- Put the Cypher and the row→typed-result deserialization in a `Query` class (see `dev/knowledge/backend/query-pattern.md`), returning a `*QueryResult` with exactly the fields the Repository needs; the Repository maps that result to the domain model. Don't return the model directly from `get_data()`.

The older `StandardNode`/`Branch` shape — persistence methods and `from_db` on the model itself — is legacy. Do not copy it into new code; when you extend an existing model that follows it, prefer adding a Repository/Query rather than another method on the model.

## Interfaces for multiple implementations

When more than one implementation of a component is required (e.g. real vs. in-memory adapter, different backends, A/B variants), define a `Protocol` or abstract base class. The correct implementation is selected at the wiring layer and injected to the constructor — the consumer codes against the interface, not a concrete class.

A single implementation does not need an interface yet; introduce one when the second implementation arrives. Note that the second implementation
can be either a no-op version (such as in the case of an enterprise-only feature) or a testing version of a component (such as in the case of an
in-memory version of a component typically backed by the database).

## Interfaces to keep an out-of-domain dependency out

The other reason to declare a `Protocol` is to invert a dependency direction, and there **one implementation is enough**. The situation: a component's logic has no business knowing about some out-of-domain concern — metrics, tracing, analytics, an audit trail, a notification service — but something has to feed that concern from inside the component's flow. Importing the client directly is what you are avoiding: it makes the dependency viral, drags a third-party package into the import chain of pure logic, and means the component can no longer be constructed in a test without it.

There are two acceptable shapes for the interface itself. Both keep the adapter and the logic from importing each other; pick one per interface and be consistent within it.

1. **Implicit — a `Protocol` declared beside the consumer, which the adapter never imports.** Structural typing is what makes this work: the adapter satisfies the protocol by having matching signatures, so nothing in the adapter's module points back at the consumer's. This is the lower-friction option: one new class, no new module, and no coordination with the adapter.
2. **Explicit — an interface in a module of its own that both sides import.** Put the `Protocol` (or an ABC, if you want subclassing enforced) in a small, dependency-free interface module; the consumer imports it to type its constructor parameter, and the adapter imports it to declare that it implements it — by subclassing the ABC, or by subclassing the `Protocol` / annotating itself against it. Neither side imports the other, so the dependency still points inward at the interface, but the contract is now named at both ends: the adapter states what it implements, `mypy` checks it at the definition rather than only at the wiring call, and a reader of the adapter can find the interface without knowing which component motivated it. Explicit is better than implicit — prefer this one whenever the interface is worth naming as a contract, which is the case as soon as it has more than one implementer or more than one consumer.

An ABC only works in shape 2 — a subclass must import whatever module the base lives in, so an ABC declared in the consumer's module drags the dependency backwards. Never do that; if you want an ABC, give it its own module.

Whichever shape you pick, the remaining two parts do not change:

- **Name the methods in the depending component's vocabulary**, not the adapter's — `on_depth_changed(*, queued: int, running: int)`, not `set_gauges(...)` — and pass the values as arguments rather than handing over `self`, so the adapter can never read back into the component. The component then depends on a shape it defined, has no idea what is on the other side, and stays free to change its internals.
- **Put the concrete adapter in a separate, purpose-named module** that is the only place importing the library, and **let only the wiring layer import both** (see "Build components near the application entry point").

The acceptance test is an import-graph one: after this, the library is reachable from the entry point and from the adapter module, and from nowhere in the logic. Verify it by grepping for the package name — if it appears anywhere under the component's own package, the split is incomplete.

This is the deliberate exception to "a single implementation does not need an interface yet" above. The interface earns its place by fixing which way the dependency points, not by abstracting over variants — and in practice the test doubles become the second and third implementations anyway.

`backend/infrahub/api/admission/` is a worked example: the decision logic, its protocols, the concrete sinks, and the factory that names them are four separate concerns in four modules.

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
