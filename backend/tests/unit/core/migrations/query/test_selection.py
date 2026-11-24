from typing import Any

import pytest

from infrahub.core.migrations.query.selection import MigrationSelectionQuery


def test_a_single_string_of_node_ids_is_refused() -> None:
    # Callers pass the IDs through untyped keyword arguments, which no type checker sees.
    kwargs: dict[str, Any] = {"node_ids": "5c1f6e0a-0000-0000-0000-00000000aaaa"}

    with pytest.raises(TypeError, match=r"^node_ids must be a collection of node IDs, not a single string$"):
        MigrationSelectionQuery(**kwargs)
