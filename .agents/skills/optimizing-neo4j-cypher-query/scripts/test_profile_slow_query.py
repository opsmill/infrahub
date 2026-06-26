#!/usr/bin/env python3
"""Stdlib tests for the query.log parser in profile_slow_query.py.

The parser is the skill's deterministic unique value, and it is tightly coupled to neo4j's
exact `query.log` line layout. If neo4j changes that format on an upgrade, the parser starts
returning None for finished-query entries and `find-slow` looks like "nothing is slow" — a
false negative. These tests pin the current format so that drift fails *here*, loudly, instead
of silently degrading the skill.

No third-party deps and no running container required — every test feeds the pure parsing
functions hand-built log text. Run directly (`python test_profile_slow_query.py`) or under
pytest (`pytest test_profile_slow_query.py`).
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

_MOD_PATH = pathlib.Path(__file__).with_name("profile_slow_query.py")
_spec = importlib.util.spec_from_file_location("profile_slow_query", _MOD_PATH)
if _spec is None or _spec.loader is None:
    msg = f"could not load module spec from {_MOD_PATH}"
    raise RuntimeError(msg)
psq = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass can resolve the module under `from __future__ import annotations`.
sys.modules[_spec.name] = psq
_spec.loader.exec_module(psq)

# A faithful single finished-query entry, matching the layout documented at the top of
# profile_slow_query.py. Two entries are concatenated to also exercise _split_entries.
FINISHED = (
    "2026-05-28 18:31:00.846+0000 INFO  id:7187 - transaction id:5344 - 42 ms: "
    "(planning: 0, waiting: 0) - 100 B - 5 page hits, 0 page faults - "
    "bolt-session\tbolt\tdriver\t\tclient\tserver> neo4j - neo4j - "
    "MATCH (n) RETURN n - {branch: 'main'} - runtime=pipelined - "
    "{name: 'node_get_list', infrahub_id: 'abcdef01'}"
)
STARTED = "2026-05-28 18:31:00.800+0000 INFO  id:7187 - transaction id:5344 - Query started: MATCH (n) RETURN n"

# Expected values embedded in FINISHED, named so the assertions read intentionally.
EXPECTED_BOLT_ID = 7187
EXPECTED_MS = 42
EXPECTED_ENTRY_COUNT = 2


def test_finished_entry_fields() -> None:
    e = psq._parse(FINISHED)
    assert e is not None, "a well-formed finished-query line must parse"
    assert e.bolt_id == EXPECTED_BOLT_ID
    assert e.ms == EXPECTED_MS
    assert e.query == "MATCH (n) RETURN n"
    assert e.params == "{branch: 'main'}"
    assert e.runtime == "pipelined"
    assert e.name == "node_get_list"
    assert e.span == "abcdef01"


def test_started_line_is_an_expected_skip_not_a_parse_failure() -> None:
    # The iterator pre-filters these; the classifier must recognise them.
    assert psq._is_started_line(STARTED) is True
    assert psq._is_started_line(FINISHED) is False


def test_format_drift_returns_none() -> None:
    # A finished-query line missing the ` - runtime=` / ` - {name:` tail is exactly the drift
    # case: it must return None (so callers can count and warn), not raise.
    drifted = (
        "2026-05-28 18:31:00.846+0000 INFO  id:9 - transaction id:1 - 10 ms: server> neo4j - neo4j - MATCH (n) RETURN n"
    )
    assert psq._parse(drifted) is None


def test_splits_on_timestamp_anchor() -> None:
    entries = psq._split_entries(STARTED + "\n" + FINISHED)
    assert len(entries) == EXPECTED_ENTRY_COUNT
    assert psq._is_started_line(entries[0]) is True
    assert psq._parse(entries[1]) is not None


def test_strips_leading_runtime_clause() -> None:
    q, stripped = psq._strip_parallel_prefix("CYPHER runtime=parallel\nMATCH (n) RETURN n")
    assert stripped is True
    assert q == "MATCH (n) RETURN n"


def test_leaves_plain_query_untouched() -> None:
    q, stripped = psq._strip_parallel_prefix("MATCH (n) RETURN n")
    assert stripped is False
    assert q == "MATCH (n) RETURN n"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
