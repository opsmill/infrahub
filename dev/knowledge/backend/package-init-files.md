# Package `__init__.py` files: no logic

**Guideline:** for new code, keep `__init__.py` files free of logic, object construction, and
definitions. Prefer an **empty** `__init__.py` and import from the submodule that owns a symbol
(`from infrahub.core.preferences.models import Preference`). Re-exporting a few submodule symbols
through `__init__.py` is allowed when a package curates a deliberately small public API, but it is
optional — not something to reach for by default, and never a reason to funnel every symbol through
the package root.

## Why

- **Import-time side effects.** Code in `__init__.py` runs whenever the package is imported (often
  transitively/early), which can trigger work before the app is ready and makes import order matter.
- **Circular imports.** This is the main reason, and it bites even with pure re-exports (no logic).
  When `__init__.py` imports from several submodules, importing *any one* symbol from the package
  forces Python to run the whole `__init__.py` — pulling in the dependencies of *every* submodule it
  re-exports. A dependency cycle in any one submodule then becomes a cycle for everyone who imports
  anything from the package. Importing from the owning submodule loads only that submodule's deps.
- **Discoverability.** Logic hidden in `__init__.py` is easy to miss; a named module (`constants.py`,
  `permissions.py`, `models.py`, …) says what it is. Importing from the owning submodule also makes
  the symbol's home obvious at the call site.

## Do

```python
# core/preferences/__init__.py is empty; callers import from the owning submodule:
from infrahub.core.preferences.models import Preference
from infrahub.core.preferences.constants import DateFormat
```

Re-exporting through `__init__.py` (imports and `__all__` only, still no logic) is tolerable when a
package curates a small public API out of a **single** submodule, since importing any of those symbols
would load that submodule's deps anyway:

```python
# core/relationship/__init__.py — re-exports from one submodule
from .model import Relationship, RelationshipCreateData, RelationshipManager

__all__ = ["Relationship", "RelationshipCreateData", "RelationshipManager"]
```

Do not aggregate re-exports **across several submodules** (`constants`, `models`, `permissions`, …)
into `__init__.py`: that is what makes importing one symbol drag in every submodule's dependencies
and turns any per-submodule cycle into a package-wide one.

## Don't

```python
# some_package/__init__.py
from infrahub.core.account import GlobalPermission
# ... logic / object construction in the package init:
SOME_PERMISSION = GlobalPermission(action=..., decision=...)  # -> move to permissions.py
```

We do have logic in `__init__.py` in a number of older places; this is the pattern to follow for new
code, and a good opportunistic cleanup when touching an existing package.
