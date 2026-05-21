# Contract — Configuration Settings

New fields on `SecuritySettings` (`backend/infrahub/config.py:743+`).

Env prefix is the existing `INFRAHUB_SECURITY_`.

## `INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER`

**Type**: `str | list[str] | None`
**Default**: `None`
**Required**: No
**Behavior**:

- Unset, empty string, whitespace-only string, or empty list → feature off. Startup proceeds normally; no warning, no error (FR-001, FR-003).
- One or more non-empty regex strings → feature on; auto-creation evaluates every external claim against the supplied patterns, in declared order, first match per claim wins (FR-005).
- Every supplied pattern is compiled with `re.compile` at config load time. Any compilation failure raises `pydantic.ValidationError` at startup; the error message MUST name the failing setting and include the regex parser error (FR-004).
- A pattern MAY include a named capture group `(?P<name>...)`. If present, the captured value is the effective local Infrahub group name (FR-006). If absent, the full matched claim string is the effective local name as-is (FR-007). Index-based capture groups are ignored for naming purposes (FR-008).
- Compiled patterns are stored on a private `SecuritySettings` attribute so the auth hook does not re-compile per request.

**Examples**:

```bash
# Single pattern, named capture
export INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER='^LDAP/group/(?P<name>.+)$'

# Multiple patterns, evaluated in order
export INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER='["^LDAP/group/(?P<name>.+)$","^azure/team/(?P<name>.+)$"]'

# Feature off (any of the four equivalents)
unset INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER
export INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER=''
export INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER='   '
export INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER='[]'
```

### Startup failure on invalid regex (FR-004)

The "fail at startup if any pattern doesn't compile" guarantee rides Infrahub's existing settings-loading pipeline. The mechanism is the same one already used elsewhere in `config.py` — see the `@model_validator` precedent at `backend/infrahub/config.py:1189-1193` (it rejects `delete_git_branch_after_merge` without `delete_branch_after_merge`). This feature does not introduce a new failure pathway; it adds one more validator that hooks into the existing one.

The chain:

```text
Server bootstrap
  └─> config.load_and_exit(...)                            # config.py:1221
       └─> load(...)                                       # config.py:1201
            └─> Settings(**toml_data) or Settings()        # config.py:1216 / 1218
                 └─> Pydantic instantiates Settings.security:   # config.py:1183
                      SecuritySettings = SecuritySettings()
                       └─> Pydantic runs every @field_validator
                            └─> @field_validator("auto_create_groups_filter")
                                 └─> re.compile(pattern)
                                      └─> re.error  ──> ValueError(...)
                                                          │
                                                          ▼
                                            pydantic.ValidationError
                                                          │
                                                          ▼
       load_and_exit catches ValidationError              # config.py:1234-1239
            ├─> prints "Configuration not valid, found N error(s)"
            ├─> prints each error: "<loc> | <msg> (<type>)"
            └─> sys.exit(1)

  → process terminates BEFORE FastAPI / Neo4j / event bus start.
```

**What this looks like to an operator** when they set a bad pattern:

```text
$ INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER='^LDAP/group/(?P<name+$' infrahub server start
Configuration not valid, found 1 error(s)
  security/auto_create_groups_filter | Invalid regex at index 0: missing ), unterminated subpattern at position 23 (value_error)
$ echo $?
1
```

The FastAPI server never binds its port; the process exits non-zero, surfacing the misconfiguration in whatever runs Infrahub (systemd, the container orchestrator, the test harness).

**Validator shape** (illustrative — final implementation follows the existing `SecuritySettings` style; the load-bearing parts are ① the validator runs at `SecuritySettings()` instantiation, ② `re.error` is caught and re-raised as `ValueError`, ③ Pydantic + `load_and_exit` do the rest):

```python
class SecuritySettings(BaseSettings):
    auto_create_groups_filter: str | list[str] | None = None
    # ... other fields ...

    @field_validator("auto_create_groups_filter")
    @classmethod
    def _compile_filter_patterns(
        cls, value: str | list[str] | None
    ) -> tuple[re.Pattern, ...]:
        if value is None or (isinstance(value, str) and not value.strip()) or value == []:
            return ()
        patterns = [value] if isinstance(value, str) else value
        compiled: list[re.Pattern] = []
        for idx, pat in enumerate(patterns):
            if not pat or not pat.strip():
                continue  # whitespace/empty entries treated as off, not a config error
            try:
                compiled.append(re.compile(pat))
            except re.error as err:
                raise ValueError(
                    f"Invalid regex at index {idx}: {err.msg} at position {err.pos}"
                ) from err
        return tuple(compiled)
```

## `INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_MAX_PER_LOGIN`

**Type**: `int`
**Default**: `50`
**Required**: No
**Behavior**: Soft cap on the number of *new* group creations attempted within a single login (FR-020). Membership additions to already-existing groups are uncounted. When the cap is reached mid-login, remaining matching claims are dropped, a single `GroupAutoCreateCapBreachEvent` is emitted carrying the cap value, the verbatim length-truncated dropped claim values, and the dropped count; the login completes successfully.

**Validation**: Must be `>= 1`. Configuration with `0` or negative is rejected at startup.
