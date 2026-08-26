from __future__ import annotations

import re

from e2e_proof_embed import ProofResult, apply_proof_sections, sanitize_reason

RUN_URL = "https://github.com/opsmill/infrahub/actions/runs/123"
IMAGE_URL = "https://raw.githubusercontent.com/opsmill/infrahub/abc123/pr-42/red-123.png"

BODY = """## Summary

Reproduction test for the widget bug.

<!-- AGENT_TEST_COMPLETE -->

<!-- cubic:analysis:start -->
Third-party bot analysis content.
<!-- cubic:analysis:end -->"""

GREEN_BODY = BODY + "\n\n<!-- AGENT_FIX_COMPLETE -->"


def _apply_red(body: str, reason: str = "test failed on its assertion", image_url: str | None = None) -> str:
    return apply_proof_sections(
        body,
        ProofResult(phase="red", verdict="red_confirmed", reason=reason, run_url=RUN_URL, image_url=image_url),
    )


def _apply_green(body: str, reason: str = "reproduction test passes") -> str:
    return apply_proof_sections(
        body,
        ProofResult(phase="green", verdict="green_confirmed", reason=reason, run_url=RUN_URL),
    )


def _section(body: str, name: str) -> str:
    match = re.search(
        f"<!-- E2E_PROOF:{name}:BEGIN -->(.*?)<!-- E2E_PROOF:{name}:END -->",
        body,
        re.DOTALL,
    )
    assert match is not None, f"section {name} missing"
    return match.group(1)


def test_sections_appended_once_when_absent() -> None:
    result = _apply_red(BODY, image_url=IMAGE_URL)
    assert result.count("<!-- E2E_PROOF:RED:BEGIN -->") == 1
    assert result.count("<!-- E2E_PROOF:NOTE:BEGIN -->") == 1
    assert "<!-- E2E_PROOF:GREEN:BEGIN -->" not in result
    assert result.startswith(BODY)
    assert "✅ `red_confirmed`" in _section(result, "RED")
    assert f"([run]({RUN_URL}))" in _section(result, "RED")
    assert f"![before]({IMAGE_URL})" in _section(result, "RED")


def test_section_replaced_in_place_when_present() -> None:
    first = _apply_red(BODY, reason="first reason")
    second = _apply_red(first, reason="second reason")
    assert second.count("<!-- E2E_PROOF:RED:BEGIN -->") == 1
    assert "second reason" in _section(second, "RED")
    assert "first reason" not in second


def test_second_identical_run_is_a_noop() -> None:
    first = _apply_red(BODY, image_url=IMAGE_URL)
    second = _apply_red(first, image_url=IMAGE_URL)
    assert second == first


def test_content_outside_markers_is_byte_identical() -> None:
    result = _apply_green(GREEN_BODY)
    assert result.startswith(GREEN_BODY)
    assert "<!-- AGENT_TEST_COMPLETE -->" in result
    assert "<!-- AGENT_FIX_COMPLETE -->" in result
    stripped = re.sub(
        r"<!-- E2E_PROOF:\w+:BEGIN -->.*?<!-- E2E_PROOF:\w+:END -->",
        "",
        result,
        flags=re.DOTALL,
    )
    assert stripped.strip() == GREEN_BODY.strip()


def test_third_party_bot_content_preserved_across_phases() -> None:
    result = _apply_green(_apply_red(BODY))
    assert "<!-- cubic:analysis:start -->\nThird-party bot analysis content.\n<!-- cubic:analysis:end -->" in result


def test_note_rewritten_on_phase_change() -> None:
    red_result = _apply_red(BODY)
    assert "expected to fail" in _section(red_result, "NOTE")
    assert "`bug-agent-e2e-proof`" in _section(red_result, "NOTE")

    green_result = _apply_green(red_result)
    assert green_result.count("<!-- E2E_PROOF:NOTE:BEGIN -->") == 1
    assert "expected to pass" in _section(green_result, "NOTE")
    assert "expected to fail" not in _section(green_result, "NOTE")
    assert "✅ `red_confirmed`" in _section(green_result, "RED")
    assert "✅ `green_confirmed`" in _section(green_result, "GREEN")


def test_unconfirmed_verdict_gets_warning_icon() -> None:
    result = apply_proof_sections(
        BODY,
        ProofResult(phase="red", verdict="does_not_reproduce", reason="test passed", run_url=RUN_URL),
    )
    assert "⚠️ `does_not_reproduce`" in _section(result, "RED")


def test_reason_is_sanitized_in_the_section() -> None:
    reason = "line one\nline two with `backticks` and [brackets](x) and <angle>"
    result = _apply_red(BODY, reason=reason)
    section = _section(result, "RED")
    assert "\\`backticks\\`" in section
    assert "\\[brackets\\]" in section
    assert "\\<angle\\>" in section
    assert "line one line two" in section


def test_sanitize_reason_truncates_and_collapses() -> None:
    sanitized = sanitize_reason("word\n" * 100)
    assert len(sanitized) == 200
    assert "\n" not in sanitized


def test_empty_body_gets_only_the_sections() -> None:
    result = _apply_red("")
    assert result.startswith("<!-- E2E_PROOF:RED:BEGIN -->")
    assert result.count("<!-- E2E_PROOF:NOTE:BEGIN -->") == 1
