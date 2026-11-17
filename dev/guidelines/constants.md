# Constants and literals

Avoid magic numbers. Create named constants for values that encode domain rules, limits, defaults,
thresholds, timeouts, retry counts, or protocol requirements. Apply this when writing and reviewing
backend and frontend code. A single use still needs a name when the literal hides its meaning or
reason for changing.

## Find and reuse the owner

Search the owning domain for an existing constant, enum, or configuration setting before introducing
a value. Reuse it wherever code implements the same rule, including equality checks, validation,
defaults, and derived calculations. Copying its current value creates a second source of truth.

When no definition exists, create one beside the code that owns the rule. Keep a constant local to
its module when only that module owns it; move it to the domain's shared constants module when
other modules need it. Name the purpose and units, such as `MAX_RETRY_ATTEMPTS` or
`DEFAULT_TIMEOUT_SECONDS`. Avoid names that merely spell out the number.

Share constants by meaning, not by coincidentally equal values. A retry count and a page size need
separate names even if both currently equal the same number. Read operator-controlled values from
configuration; do not copy their defaults into constants at call sites.

For example:

```python
# Bad: the retry policy is hidden in the comparison.
if attempts >= 3:
    stop_retrying()

# Good: define the policy once and reuse its name.
MAX_RETRY_ATTEMPTS = 3

if attempts >= MAX_RETRY_ATTEMPTS:
    stop_retrying()
```

Follow the language's [Python naming rules](backend/python.md#naming-conventions) or
[TypeScript naming rules](frontend/typescript.md#constants). Use an existing enum for a closed set of
named states rather than adding parallel string constants.

## Keep literals when they express the structure

Keep obvious indexes, empty values, fixed tuple shapes, and arithmetic identities literal when their
meaning is clear from the operation. Do not extract every `0`, `1`, or string into a constant.
Check what the value means: a domain limit needs a name even when its value happens to be `1`.

Keep test expectations independent of production constants when the test verifies the value of a
contract. Importing that constant as the expected value can make the test pass when the contract
changes incorrectly. See [independent expected values](backend/testing.md#assert-exact-expectations).

## Review touched code

Before finishing a change, inspect new or changed literals and their callers. Confirm that each
domain value has one owner, callers reuse its name, and names explain the value's purpose and units.
Check both sides of a comparison and any derived defaults; replacing only the rejection threshold
can leave another copy in the accepted path.
