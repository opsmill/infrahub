from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Tuple

from infrahub_sdk import Timestamp as BaseTimestamp

if TYPE_CHECKING:
    from pendulum.datetime import DateTime


class Timestamp(BaseTimestamp):
    async def to_graphql(self, *args: Any, **kwargs: Any) -> DateTime:  # pylint: disable=unused-argument
        return self.obj

    def get_query_filter_path(self, rel_name: str = "r") -> Tuple[str, Dict]:
        """
        Generate a CYPHER Query filter based on a path to query a part of the graph at a specific time on all branches.

        There is a currently an assumption that the relationship in the path will be named 'r'
        """

        params = {"at": self.to_string()}

        filters = [
            f"({rel_name}.from <= $at AND {rel_name}.to IS NULL)",
            f"({rel_name}.from <= $at AND {rel_name}.to >= $at)",
        ]
        filter_str = "(" + "\n OR ".join(filters) + ")"

        return filter_str, params


def current_timestamp() -> str:
    return Timestamp().to_string()
