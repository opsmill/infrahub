"""Long Text attribute values must stay fully readable in the create/edit form.

The field has to wrap or grow instead of clipping the value at its right edge.
Playwright's to_be_visible() cannot catch this class of bug (the full value is
in the DOM, the element is visible, only the rendering clips), so the probe
scrolls the field horizontally -- a field that can scroll sideways is a field
that clips its value. Needs only the core schema (BuiltinTag) and never
submits, hence no data fixtures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from playwright.async_api import Page

# A 111-character example, well under the attribute's limit.
LONG_DESCRIPTION = (
    "Very long description that is still smaller than the current limit of 128 characters. Would be good to fix that"
)


class TestLongTextAttribute:
    async def test_long_description_is_fully_visible_in_create_form(self, admin_page: Page) -> None:
        await admin_page.goto("/objects/BuiltinTag")
        await admin_page.get_by_test_id("create-object-button").click()
        await expect(admin_page.get_by_text("Create Tag")).to_be_visible()

        description_field = admin_page.get_by_label("Description")
        await description_field.fill(LONG_DESCRIPTION)
        await expect(description_field).to_have_value(LONG_DESCRIPTION)

        hidden_px = await description_field.evaluate(
            "el => { el.scrollLeft = 1e6; const left = el.scrollLeft; el.scrollLeft = 0; return left; }"
        )
        assert hidden_px == 0, (
            f"Description field clips its value: {hidden_px}px of the "
            f"{len(LONG_DESCRIPTION)}-char text is hidden beyond the field's right edge"
        )
