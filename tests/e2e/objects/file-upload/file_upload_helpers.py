"""Port of frontend/app/tests/e2e/objects/file-upload/file-upload-helpers.ts.

Sibling helper module for test_file_upload.py: upload a file through the form's
``input[type="file"]`` and fill the InfraCircuitContract required fields.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

# Common file types for testing (port of TEST_FILE_TYPES).
TEST_FILE_TYPES = {
    "TEXT": {"mime_type": "text/plain", "extension": ".txt"},
    "JSON": {"mime_type": "application/json", "extension": ".json"},
    "YAML": {"mime_type": "application/x-yaml", "extension": ".yaml"},
    "CSV": {"mime_type": "text/csv", "extension": ".csv"},
    "PDF": {"mime_type": "application/pdf", "extension": ".pdf"},
    "PNG": {"mime_type": "image/png", "extension": ".png"},
    "JPEG": {"mime_type": "image/jpeg", "extension": ".jpg"},
}


def upload_file(
    page: Page, *, name: str, mime_type: str, content: str | None = None, buffer: bytes | None = None
) -> None:
    """Upload a file using Playwright's set_input_files.

    Accepts either raw ``content`` (encoded to bytes) or an already built
    ``buffer``, mirroring the TS helper's two-shape signature.
    """
    file_input = page.locator('input[type="file"]')
    payload = buffer if buffer is not None else (content or "").encode()
    file_input.set_input_files(files={"name": name, "mimeType": mime_type, "buffer": payload})


def generate_test_file_content(size: str = "small") -> str:
    """Generate a test file with repeated content (port of generateTestFileContent)."""
    sizes = {
        "small": 100,  # ~100 bytes
        "medium": 1024,  # ~1KB
        "large": 10_240,  # ~10KB
    }
    target_size = sizes[size]
    line = "This is a test line of content.\n"
    repeat_count = math.ceil(target_size / len(line))
    return line * repeat_count


def create_test_file(
    file_name: str,
    file_type: str = "TEXT",
    content: str | None = None,
) -> dict[str, object]:
    """Create a test file buffer from template (port of createTestFile)."""
    type_info = TEST_FILE_TYPES[file_type]
    default_content = content if content is not None else generate_test_file_content("small")
    return {
        "name": file_name,
        "mime_type": type_info["mime_type"],
        "buffer": default_content.encode(),
    }


def fill_circuit_contract_fields(
    page: Page,
    *,
    contract_number: str | None = None,
    vendor: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> None:
    """Fill required fields for InfraCircuitContract (port of fillCircuitContractFields)."""
    defaults = {
        "contract_number": contract_number if contract_number is not None else f"CONTRACT-{int(time.time() * 1000)}",
        "vendor": vendor if vendor is not None else "Test Vendor Inc",
        "start_date": start_date if start_date is not None else "2024-01-01",
        "end_date": end_date if end_date is not None else "2025-12-31",
    }

    form = page.get_by_test_id("side-panel-container")

    # Wait for form to be ready
    form.get_by_label("Contract Number").wait_for(state="visible")

    form.get_by_label("Contract Number").fill(defaults["contract_number"])
    form.get_by_label("Vendor").fill(defaults["vendor"])
    form.get_by_label("Start Date").fill(defaults["start_date"])
    form.get_by_label("End Date").fill(defaults["end_date"])
