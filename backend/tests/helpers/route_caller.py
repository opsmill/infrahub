from __future__ import annotations

from types import SimpleNamespace
from typing import Any

CALLER_REQUEST: Any = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(service=SimpleNamespace(cache=None))))
"""What a route reads from the request when a test calls it as a function: the cache of the merge write blocker."""
CALLER_ACCOUNT: Any = SimpleNamespace(account_id="caller")
"""The account a route reads the identifier of when a test calls it as a function."""
