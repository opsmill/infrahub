"""Port of frontend/app/tests/e2e/objects/file-upload/file-upload-helpers.ts.

Sibling helper module for test_file_upload.py: upload a file through the form's
``input[type="file"]`` and fill the InfraCircuitContract required fields.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

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


async def upload_file(
    page: Page, *, name: str, mime_type: str, content: str | None = None, buffer: bytes | None = None
) -> None:
    """Upload a file using Playwright's set_input_files.

    Accepts either raw ``content`` (encoded to bytes) or an already built
    ``buffer``, mirroring the TS helper's two-shape signature.
    """
    file_input = page.locator('input[type="file"]')
    payload = buffer if buffer is not None else (content or "").encode()
    await file_input.set_input_files(files={"name": name, "mimeType": mime_type, "buffer": payload})


def create_minimal_pdf_buffer(text: str = "Mock PDF content for E2E testing") -> bytes:
    """Build a valid, minimal single-page PDF (port of createMinimalPdfBuffer).

    The browser's PDF viewer (PDFium) validates the document structure when a saved file is
    previewed in an ``<iframe src="data:application/pdf;...">``. Uploading plain text with an
    ``application/pdf`` mime type makes the viewer fail with "Failed to load PDF document", so
    PDF upload tests must use real PDF bytes. Byte offsets in the xref table are computed from
    the encoded body, mirroring the TS helper's ``Buffer.byteLength``.
    """
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 18 Tf 36 100 Td ({escaped}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Resources "
        "<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream.encode())} >>\nstream\n{stream}\nendstream",
    ]

    body = "%PDF-1.4\n"
    offsets: list[int] = []
    for index, obj in enumerate(objects):
        offsets.append(len(body.encode()))
        body += f"{index + 1} 0 obj\n{obj}\nendobj\n"

    xref_offset = len(body.encode())
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        xref += f"{offset:010d} 00000 n \n"
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"

    return (body + xref + trailer).encode()


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


async def fill_circuit_contract_fields(
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
    await form.get_by_label("Contract Number").wait_for(state="visible")

    await form.get_by_label("Contract Number").fill(defaults["contract_number"])
    await form.get_by_label("Vendor").fill(defaults["vendor"])
    await form.get_by_label("Start Date").fill(defaults["start_date"])
    await form.get_by_label("End Date").fill(defaults["end_date"])
