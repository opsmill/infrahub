# Python Typing

> Part of: `dev/guidelines/backend/` | Related: [Python Standards](python.md)

Typing rules for the Python backend. The hard rules — no new suppression, no `cast()`, `isinstance`
over `getattr` — live in `.agents/rules/python-typing.md`; this page is their fuller reference.

- All function parameters and return types must be type-hinted
- Use `str | None` for optional strings (Python 3.10+)
- Use `list[Type]` instead of `List[Type]` (Python 3.9+)

## Type a closed value set as an enum, not `str`

When a field or argument accepts only a fixed set of values, don't type it as a bare `str` — a bare `str` lets a typo through silently and hides the valid set from readers and from the schema. Use one of:

- **`Literal["a", "b"]`** — the lighter option for a small closed set used in a **single file**. Still type-checked, no class to declare.
- **An enum** — when the set is shared across modules, needs a name, round-trips through the database, or is exposed over GraphQL. Subclass `str` so the value round-trips as text — `StrEnum` on the backend (Python 3.11+); use `class X(str, Enum)` for code shared with `python_testcontainers` (which targets 3.10).

A value that also leaves the process as an external label — a metric label, a response field, a log key — is shared by definition, so it gets the enum even if only one module reads it today. Note that second role in the enum's docstring, and pass the member itself at the emit site rather than a parallel string literal, so the exported set and the branched-on set cannot drift apart.

```python
# ❌ Bad - any string is accepted; a typo silently bypasses downstream logic
origin: str | None = None

# ✅ Good - the valid set is discoverable and reusable; the owning model validates input
class NodeMutationOrigin(StrEnum):
    LIVE = "live"
    MERGE = "merge"
    REBASE = "rebase"

origin: NodeMutationOrigin | None = None
```

The annotation alone does not reject a bad value at runtime — a validation layer enforces it (a Pydantic model, or an explicit `NodeMutationOrigin(value)` conversion at the boundary for plain dataclasses/adapters). For a value exposed over GraphQL, reuse the existing Python-enum → GraphQL-enum conversion rather than re-declaring the values as strings in the GraphQL layer.

The same applies on the read side: where an enum exists, branch on the member (`if rel.cardinality == RelationshipCardinality.MANY`), never on its string value — a comparison or query literal that hardcodes the value drifts silently when the enum changes.

## A struct of mode flags is a union of dataclasses

When a class carries several booleans of which most combinations are invalid (one flag excludes the others, two only make sense together), name the legal states instead: model each legal case as its own small dataclass and type the value as their union. Invalid combinations become unrepresentable, each case carries a name, and a `match` over the union replaces flag-order-sensitive `if` chains.

```python
# ❌ Bad - widen=True silently makes the other flags meaningless
@dataclass
class _Selection:
    widen: bool = False
    self_ids: bool = False
    reader_lookup: bool = False

# ✅ Good - each legal case is a type; invalid mixes cannot be built
@dataclass(frozen=True)
class Widen: ...

@dataclass(frozen=True)
class SelfTarget:
    ids: list[str]

@dataclass(frozen=True)
class ReaderLookup:
    reader_kind: str

Selection = Widen | SelfTarget | ReaderLookup
```

## Do not narrow a type in an override (Liskov / `ty`)

An override may not make a parameter type *narrower* (or a return type *wider*) than the base declaration — `ty` rejects it as a Liskov violation. When an abstract method and its implementations must accept a union, declare the full shared type on the abstract **and** on every implementation; do not tighten one adapter.

```python
# ❌ Bad - RedisCache narrows the abstract's `int` to `KVTTL`; ty errors
class InfrahubCache(ABC):
    async def set(self, key: str, value: str, expires: int | None = None) -> None: ...
class RedisCache(InfrahubCache):
    async def set(self, key: str, value: str, expires: KVTTL | None = None) -> None: ...

# ✅ Good - the shared union on the base and all adapters
async def set(self, key: str, value: str, expires: KVTTL | int | None = None) -> None: ...
```

## Prefer `isinstance` over `getattr` for narrowing

To branch on or read from a typed object, use `isinstance` so the type checker can narrow it; reaching for `getattr(obj, "attr", default)` defeats type analysis. When guarding a schema object, cover the whole family that carries the attribute — `isinstance(schema, (NodeSchema, ProfileSchema, TemplateSchema))` — since profiles and templates inherit node behavior and a `NodeSchema`-only check silently drops them.

The same goes for named accessors: read a relationship manager with `node.get_relationship(name)`, not `getattr(node, name)` — the accessor is typed and greppable, and `getattr` hides the read from both. When the field is optional, use the raising accessor instead of coercing: `str(rel_schema.identifier)` turns a missing identifier into the literal string `"None"`, which then matches nothing downstream — `rel_schema.get_identifier()` raises at the fault instead.

## Narrow with a check that returns the value, never with `cast()`

`cast()` is a suppression, not a narrowing tool: like an inline `# type: ignore` or a
`disable_error_code` entry, it asserts what the checker could not verify, exactly where a bug would
hide. Narrow a union with a positive `isinstance` on the type you need and return the narrowed value.
The same check then rejects an object outside the declared union, which narrowing by elimination
lets through to fail later as an `AttributeError`:

```python
# ❌ Bad - rules out the other members, then asserts what is left
if connection is None or isinstance(connection, redis.Redis):
    raise TypeError(f"expected an InfrahubServices connection, got {type(connection).__name__}")
return cast("InfrahubServices", connection)

# ✅ Good - the check itself narrows, and a foreign object fails here too
if not isinstance(connection, InfrahubServices):
    raise TypeError(f"expected an InfrahubServices connection, got {type(connection).__name__}")
return connection
```

Elimination is also what made the `cast()` look necessary: mypy does not subtract a generic class
such as `redis.Redis` from a union on the negative branch, so the leftover never narrows. A `cast()`
that "only records" what a check above established is still a `cast()` — make the check return the value.

Two signs that you are reaching for the escape hatch instead of the fix:

- **The real check trips the checker in files you did not touch.** An import added for a runtime
  `isinstance` can change the order in which mypy resolves an import cycle; errors that appear
  elsewhere are a second defect to root-cause — usually an ambiguous import, see
  [Imports](python.md#imports) — not a reason to fall back.
- **The suppression needs a paragraph.** A `# type: ignore[code]` carries its reason on the same
  line; when justifying one takes a docstring, remove it instead of documenting it.

## Don't write "one or many" unions — take the plural form and let callers wrap

A parameter typed `T | Sequence[T]` forces runtime `isinstance` dispatch on every consumer, and when `T` includes `str` the dispatch is a trap: a bare string satisfies `Sequence[str]`, so it falls into the "many" branch and gets iterated character-by-character. Declare the plural form only — `list[str]` or `tuple[str]` — and have callers pass `[value]`.
Prefer a concrete container over `Sequence[str]` when the element type is or includes `str`: mypy
rejects a bare `str` for `list[str]`, but accepts it for `Sequence[str]`, so the annotation alone
still lets the character-iteration bug through. Reserve `Sequence[T]` for a parameter that
deliberately accepts any sequence of a non-string `T`. In existing code that already carries such a union, exclude `str` before the `Sequence` check (`if isinstance(data, str) or not isinstance(data, Sequence): data = [data]`), and whenever an annotation widens, widen the runtime check in step and test with a bare `str` and a `tuple`.

## When a wrong-type bug slips through

`mypy` and `ty` both gate CI, but modules opt out of checks — mypy via per-module `disable_error_code` in `pyproject.toml`, ty via directory `[[tool.ty.overrides]]` (`invalid-argument-type` is currently ignored tree-wide). These suppressions hide real bugs.

So when a bug is caused by a **wrong type being passed** (e.g. a class where a `str` was expected), the checker should have caught it — treat it as a gap to close, not just a runtime fix:

1. Find why it was missed — usually `arg-type` / `invalid-argument-type` is suppressed for that module.
2. Re-enable the rule for that module and fix the whole typing chain it surfaces. A scoped `# type: ignore[code]  # reason` may grandfather a **pre-existing** violation that is unrelated to the fix and too wide to take on now — the rule turns on today and the debt stays visible line by line, which beats leaving the rule off. It never covers a violation your change introduces, and `cast()` is never the alternative.
3. Fix the source. Never widen a parameter's type to silence the checker when the real contract is narrower — that entrenches the defect. mypy enforces argument types by default (modules opt out), so fix there; re-enabling ty's `invalid-argument-type` is a deliberate directory-wide effort, not a per-file exception.
