import hashlib
import json
from typing import Any


class FlowRunCountCacheKeyBuilder:
    """Derive a stable cache key for a flow-run count request from its filter body."""

    def build(self, body: dict[str, Any]) -> str:
        serialized = json.dumps(body, sort_keys=True, separators=(",", ":"))
        hashed = hashlib.sha256(serialized.encode()).hexdigest()
        return f"task_manager:flow_run_count:{hashed}"
