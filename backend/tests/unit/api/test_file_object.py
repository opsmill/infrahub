from __future__ import annotations

import re

import pytest

from infrahub.api.storage.file_object import build_content_disposition, sanitize_filename


def test_sanitize_simple_filename() -> None:
    """Test that simple ASCII filenames pass through unchanged."""
    ascii_name, encoded_name = sanitize_filename("document.pdf")
    assert ascii_name == "document.pdf"
    assert encoded_name == "document.pdf"


def test_sanitize_strips_control_characters() -> None:
    """Test that control characters (CR, LF, NULL) are removed."""
    ascii_name, _ = sanitize_filename("file\r\nname\x00.txt")
    assert "\r" not in ascii_name
    assert "\n" not in ascii_name
    assert "\x00" not in ascii_name
    assert ascii_name == "filename.txt"


def test_sanitize_replaces_quotes_and_semicolons() -> None:
    """Test that quotes and semicolons are replaced to prevent header injection."""
    ascii_name, _ = sanitize_filename('file"name;test.pdf')
    assert '"' not in ascii_name
    assert ";" not in ascii_name
    assert ascii_name == "file'name_test.pdf"


def test_sanitize_truncates_long_filename() -> None:
    """Test that very long filenames are truncated to 255 characters."""
    long_name = "a" * 300 + ".pdf"
    ascii_name, _ = sanitize_filename(long_name)
    assert len(ascii_name) <= 255
    assert ascii_name.endswith(".pdf")


def test_sanitize_truncates_long_filename_without_extension() -> None:
    """Test truncation of long filenames without extension."""
    long_name = "a" * 300
    ascii_name, _ = sanitize_filename(long_name)
    assert len(ascii_name) == 255


def test_sanitize_unicode_filename() -> None:
    """Test handling of Unicode characters in filename."""
    ascii_name, encoded_name = sanitize_filename("文档.pdf")
    # ASCII version should replace non-ASCII with underscores
    assert "文" not in ascii_name
    # Encoded version should be percent-encoded
    assert encoded_name == "%E6%96%87%E6%A1%A3.pdf"


def test_sanitize_mixed_unicode_ascii() -> None:
    """Test handling of mixed Unicode and ASCII characters."""
    ascii_name, encoded_name = sanitize_filename("report_2024_日本語.pdf")
    # ASCII name has replacements
    assert "日" not in ascii_name
    assert "_" in ascii_name
    # Encoded has percent encoding for Unicode
    assert encoded_name == "report_2024_%E6%97%A5%E6%9C%AC%E8%AA%9E.pdf"


def test_content_disposition_simple_filename() -> None:
    """Test Content-Disposition for simple ASCII filename."""
    header = build_content_disposition("document.pdf")
    assert header.startswith("attachment;")
    assert 'filename="document.pdf"' in header
    assert "filename*=UTF-8''document.pdf" in header


def test_content_disposition_unicode_filename() -> None:
    """Test Content-Disposition for Unicode filename."""
    header = build_content_disposition("文档.pdf")
    assert header.startswith("attachment;")
    # Should have ASCII fallback
    assert 'filename="' in header
    # Should have RFC5987 encoded version
    assert "filename*=UTF-8''" in header
    assert "%E6%96%87%E6%A1%A3.pdf" in header


@pytest.mark.parametrize(
    "filename",
    [
        'file"name.pdf',  # Quote injection
        "file;name.pdf",  # Semicolon injection
        "file\r\nname.pdf",  # CRLF injection
        "file\x00name.pdf",  # NULL byte injection
    ],
)
def test_content_disposition_prevents_header_injection(filename: str) -> None:
    """Test that Content-Disposition header is safe from injection attacks."""
    header = build_content_disposition(filename)
    # Should not contain unescaped dangerous characters
    assert "\r" not in header
    assert "\n" not in header
    assert "\x00" not in header
    # Header should match expected format with properly quoted filename
    assert re.match(r'^attachment; filename="[^"]*"; filename\*=UTF-8\'\'.*$', header)
