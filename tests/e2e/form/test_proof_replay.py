"""Deliberately failing reproduction used to validate the bug-agent-e2e-proof workflow.

Scratch replay artifact for the quickstart of dev/specs/005-e2e-proof-runs:
the RED phase must classify the assertion failure below as red_confirmed,
the follow-up commit flips the assertion for the GREEN phase, and a final
deletion-only push validates the demotion skip. The PR is closed afterwards.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from playwright.async_api import Page


class TestProofReplay:
    async def test_tag_list_heading_is_visible(self, admin_page: Page) -> None:
        await admin_page.goto("/objects/BuiltinTag")
        await expect(admin_page.get_by_test_id("create-object-button")).to_be_visible()
        heading_count = await admin_page.get_by_role("heading", name="Tag").count()
        assert heading_count >= 1, f"replay reproduction: expected at least one Tag heading, found {heading_count}"
