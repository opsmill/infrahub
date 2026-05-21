# Contract: Error-Pattern Registry (Story 2, FR-005)

**Path**: `backend/infrahub/git/errors.py`.

## Types

```python
@dataclass(frozen=True, slots=True)
class ErrorContext:
    name: str
    branch_name: str | None = None
    location: str | None = None

Matcher = Callable[[str], bool]
ExceptionFactory = Callable[[ErrorContext, GitCommandError], Exception]

@dataclass(frozen=True, slots=True)
class ErrorRule:
    matcher: Matcher
    factory: ExceptionFactory

def any_substring(*needles: str) -> Matcher: ...
def any_substring_ci(*needles: str) -> Matcher: ...
def all_substrings(*needles: str) -> Matcher: ...
```

## Builders

Each builder is a small named module-level function. Builders are reused across rules
where the resulting exception is the same — today's `if`-chain raises
`RepositoryConnectionError(identifier=name)` from three distinct branches, and one
named builder serves all three.

```python
def _connection_error(ctx: ErrorContext, _exc: GitCommandError) -> Exception:
    return RepositoryConnectionError(identifier=ctx.name)

def _credentials_error(ctx: ErrorContext, _exc: GitCommandError) -> Exception:
    return RepositoryCredentialsError(identifier=ctx.name)

def _invalid_branch_error(ctx: ErrorContext, _exc: GitCommandError) -> Exception:
    return RepositoryInvalidBranchError(
        identifier=ctx.name, branch_name=ctx.branch_name, location=ctx.location,
    )

def _merge_repository_error(ctx: ErrorContext, exc: GitCommandError) -> Exception:
    return RepositoryError(identifier=ctx.name, message=exc.stderr)
```

## Registry

```python
ERROR_RULES: tuple[ErrorRule, ...] = (
    ErrorRule(
        matcher=any_substring(
            "Repository not found",
            "does not appear to be a git",
            "Failed to connect to",
        ),
        factory=_connection_error,
    ),
    ErrorRule(
        matcher=any_substring("error: pathspec"),
        factory=_invalid_branch_error,
    ),
    ErrorRule(
        matcher=any_substring("SSL certificate problem", "server certificate verification failed"),
        factory=_connection_error,
    ),
    ErrorRule(
        matcher=any_substring_ci("authentication failed for"),
        factory=_credentials_error,
    ),
    ErrorRule(
        matcher=all_substrings(
            "fatal: could not read Username for",
            "terminal prompts disable",
        ),
        factory=_credentials_error,
    ),
    ErrorRule(
        matcher=any_substring(
            "Need to specify how to reconcile",
            "because you have unmerged files",
        ),
        factory=_merge_repository_error,
    ),
)

def raise_enriched(error: GitCommandError, *, context: ErrorContext) -> NoReturn:
    for rule in ERROR_RULES:
        if rule.matcher(error.stderr):
            raise rule.factory(context, error) from error
    raise RepositoryError(identifier=context.name, message=error.stderr) from error
```

## Behavior parity (FR-014)

The semantics are identical to today's `_raise_enriched_error_static` (`base.py:1083-1115`):

- Same rule order (top-to-bottom of the current `if` chain).
- Same exception types in the same arguments.
- Same fallthrough generic `RepositoryError(identifier, message=stderr)`.
- Same case-sensitivity (the current code uses `.lower()` for the "authentication failed" check; the registry uses `any_substring_ci` to mirror it).

## Registering a new pattern (FR-005 acceptance)

Adding `"too many redirects"` → `RepositoryConnectionError` — the builder already exists, so this is a one-line registry append:

```python
# Open errors.py, add ONE entry to ERROR_RULES tuple. No function-body edit.
ErrorRule(matcher=any_substring("too many redirects"), factory=_connection_error),
```

Adding a pattern that needs a new exception class: add one named builder plus one registry entry. `raise_enriched` still does not change.

## Migration

The base class's existing `_raise_enriched_error_static` becomes a one-line shim that calls `raise_enriched(...)`. Inline callers stay unchanged (FR-014). The shim is removed in a follow-up PR once all callers have been switched to import `raise_enriched` directly — that follow-up is in-scope for this work if it lands naturally during one of the structural PRs; otherwise it is left to a cleanup PR.

## Verification

- A unit test in `backend/tests/unit/git/test_errors.py` exercises each rule with a fixture `stderr` string and asserts the exception type, message, and `__cause__`.
- A parity test asserts that calling `raise_enriched` and `InfrahubRepositoryBase._raise_enriched_error_static` on the same input produces equivalent exception objects (same type, same args) — until the shim is removed.
- The "add one entry, no function edit" property is the structural test: SC-007 reviewer-checks that the registration was data-only.
