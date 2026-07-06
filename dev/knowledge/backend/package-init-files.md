# Package `__init__.py` files: re-exports only

**Guideline:** for new code, keep `__init__.py` files as pure aggregation — imports and `__all__`
only. Do **not** put logic, object construction, or definitions directly in `__init__.py`.

## Why

- **Import-time side effects.** Code in `__init__.py` runs whenever the package is imported (often
  transitively/early), which can trigger work before the app is ready and makes import order matter.
- **Circular imports.** Definitions in `__init__.py` are a common source of import cycles, because the
  package is imported for its submodules but now also carries logic that itself imports other things.
- **Discoverability.** Logic hidden in `__init__.py` is easy to miss; a named module (`constants.py`,
  `permissions.py`, `models.py`, …) says what it is.

## Do

```python
# core/preferences/__init__.py
from .constants import DEFAULT_DATE_FORMAT, DateFormat
from .models import Preference
from .permissions import MANAGE_GLOBAL_PREFERENCES_PERMISSION

__all__ = ["DEFAULT_DATE_FORMAT", "MANAGE_GLOBAL_PREFERENCES_PERMISSION", "DateFormat", "Preference"]
```

## Don't

```python
# core/preferences/__init__.py
from infrahub.core.account import GlobalPermission
# ... logic / object construction in the package init:
MANAGE_GLOBAL_PREFERENCES_PERMISSION = GlobalPermission(action=..., decision=...)  # -> move to permissions.py
```

We do have logic in `__init__.py` in a number of older places; this is the pattern to follow for new
code, and a good opportunistic cleanup when touching an existing package.
