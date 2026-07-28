from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from infrahub.core.merge.follow_up import merge_follow_up_guard

if TYPE_CHECKING:
    import pytest


def test_merge_follow_up_guard_absorbs_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)
    log = logging.getLogger("test_merge_follow_up_guard")
    ran_after = False

    with merge_follow_up_guard(log, "follow-up failed"):
        raise RuntimeError("boom")
    ran_after = True

    assert ran_after is True
    assert [record.message for record in caplog.records] == ["follow-up failed"]
    assert caplog.records[0].exc_info is not None


def test_merge_follow_up_guard_no_error_stays_silent(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)
    log = logging.getLogger("test_merge_follow_up_guard")
    calls: list[str] = []

    with merge_follow_up_guard(log, "follow-up failed"):
        calls.append("ran")

    assert calls == ["ran"]
    assert caplog.records == []
