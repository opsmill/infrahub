from tests.db_snapshot import DbSnapshot


def assert_edge_timestamps(
    before_snapshot: DbSnapshot,
    after_snapshot: DbSnapshot,
    expected_timestamp: str,
) -> None:
    """Verify all new/modified edges use the expected timestamp.

    For new edges: 'from' must equal expected_timestamp
    For modified edges: changed 'to' must equal expected_timestamp
    """
    before_edges_by_id = {e.db_id: e for e in before_snapshot.edge_map.values()}
    after_edges_by_id = {e.db_id: e for e in after_snapshot.edge_map.values()}

    for edge_id, after_edge in after_edges_by_id.items():
        before_edge = before_edges_by_id.get(edge_id)

        if before_edge is None:
            # New edge - 'from' must equal expected_timestamp
            from_time = after_edge.properties.get("from")
            assert from_time == expected_timestamp, (
                f"New edge {after_edge.edge_type} has from={from_time}, expected {expected_timestamp}"
            )
        else:
            # Check for modified 'to' time (from never changes once set)
            before_to = before_edge.properties.get("to")
            after_to = after_edge.properties.get("to")

            if before_to != after_to:
                assert after_to == expected_timestamp, (
                    f"Modified edge {after_edge.edge_type} has to={after_to}, expected {expected_timestamp}"
                )
