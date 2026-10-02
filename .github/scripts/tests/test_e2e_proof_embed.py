from __future__ import annotations

import re

import e2e_proof_embed
import pytest
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


def test_mid_body_section_replaced_in_place_with_trailing_prose_intact() -> None:
    body = (
        "Intro paragraph.\n\n"
        "<!-- E2E_PROOF:RED:BEGIN -->\nstale content\n<!-- E2E_PROOF:RED:END -->\n\n"
        "Trailing prose that must survive."
    )
    result = _apply_red(body, reason="fresh reason")
    assert result.startswith("Intro paragraph.\n\n<!-- E2E_PROOF:RED:BEGIN -->")
    assert "stale content" not in result
    assert "fresh reason" in _section(result, "RED")
    assert "<!-- E2E_PROOF:RED:END -->\n\nTrailing prose that must survive." in result
    assert result.index("<!-- E2E_PROOF:RED:BEGIN -->") < result.index("Trailing prose that must survive.")


def test_green_image_url_gets_the_after_label() -> None:
    result = apply_proof_sections(
        BODY,
        ProofResult(phase="green", verdict="green_confirmed", reason="passes", run_url=RUN_URL, image_url=IMAGE_URL),
    )
    assert f"![after]({IMAGE_URL})" in _section(result, "GREEN")


def test_orphaned_begin_marker_is_repaired_and_user_content_preserved() -> None:
    body = "Intro.\n\n<!-- E2E_PROOF:RED:BEGIN -->\nUser content stranded after an orphaned marker.\n\nMore user prose."
    result = _apply_red(body, reason="fresh reason")
    assert "User content stranded after an orphaned marker." in result
    assert "More user prose." in result
    assert result.count("<!-- E2E_PROOF:RED:BEGIN -->") == 1
    assert result.count("<!-- E2E_PROOF:RED:END -->") == 1
    assert "fresh reason" in _section(result, "RED")
    assert result.index("More user prose.") < result.index("<!-- E2E_PROOF:RED:BEGIN -->")


def test_orphaned_begin_before_a_complete_pair_does_not_swallow_user_content() -> None:
    body = (
        "Intro.\n\n"
        "<!-- E2E_PROOF:RED:BEGIN -->\n"
        "User content between an orphan and a real pair.\n\n"
        "<!-- E2E_PROOF:RED:BEGIN -->\nold section\n<!-- E2E_PROOF:RED:END -->\n\n"
        "Closing prose."
    )
    result = _apply_red(body, reason="fresh reason")
    assert "User content between an orphan and a real pair." in result
    assert "Closing prose." in result
    assert result.count("<!-- E2E_PROOF:RED:BEGIN -->") == 1
    assert result.count("<!-- E2E_PROOF:RED:END -->") == 1
    assert "fresh reason" in _section(result, "RED")
    # The repair only strips markers: the stale pair's inner text stays as
    # plain body text rather than risking a delete of user content.
    assert "old section" in result
    assert "old section" not in _section(result, "RED")


_MAIN_ARGS = [
    "--repo",
    "opsmill/infrahub",
    "--pr",
    "42",
    "--phase",
    "red",
    "--verdict",
    "red_confirmed",
    "--reason",
    "test failed on its assertion",
    "--run-url",
    RUN_URL,
]


def test_main_never_patches_an_already_current_body(monkeypatch: pytest.MonkeyPatch) -> None:
    current = _apply_red(BODY)
    patches: list[str] = []
    monkeypatch.setattr(e2e_proof_embed, "_fetch_body", lambda _repo, _pr: current)
    monkeypatch.setattr(e2e_proof_embed, "_patch_body", lambda _repo, _pr, body: patches.append(body))
    assert e2e_proof_embed.main(_MAIN_ARGS) == 0
    assert patches == []


def test_main_marker_loss_race_is_retried_once_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fetches: list[int] = []
    patches: list[str] = []

    def fake_fetch(_repo: str, _pr: int) -> str:
        fetches.append(1)
        # Odd fetches feed the transform; even fetches verify the PATCH and
        # simulate a concurrent editor's stale write dropping the marker.
        if len(fetches) % 2 == 1:
            return BODY
        return "A stale body without the pipeline phase markers."

    monkeypatch.setattr(e2e_proof_embed, "_fetch_body", fake_fetch)
    monkeypatch.setattr(e2e_proof_embed, "_patch_body", lambda _repo, _pr, body: patches.append(body))
    with pytest.raises(RuntimeError, match="AGENT_TEST_COMPLETE"):
        e2e_proof_embed.main(_MAIN_ARGS)
    assert len(patches) == 2
    assert len(fetches) == 4


def test_main_marker_loss_race_recovers_on_the_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    fetches: list[int] = []
    patches: list[str] = []

    def fake_fetch(_repo: str, _pr: int) -> str:
        fetches.append(1)
        if len(fetches) == 2:
            return "A stale body without the pipeline phase markers."
        if len(fetches) == 4:
            return patches[-1]
        return BODY

    monkeypatch.setattr(e2e_proof_embed, "_fetch_body", fake_fetch)
    monkeypatch.setattr(e2e_proof_embed, "_patch_body", lambda _repo, _pr, body: patches.append(body))
    assert e2e_proof_embed.main(_MAIN_ARGS) == 0
    assert len(patches) == 2


def test_gh_calls_carry_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    timeouts: list[object] = []

    class FakeCompleted:
        stdout = '{"body": ""}'

    def fake_run(_cmd: list[str], **kwargs: object) -> FakeCompleted:
        timeouts.append(kwargs.get("timeout"))
        return FakeCompleted()

    monkeypatch.setattr(e2e_proof_embed.subprocess, "run", fake_run)
    e2e_proof_embed._fetch_body("opsmill/infrahub", 42)  # noqa: SLF001
    e2e_proof_embed._patch_body("opsmill/infrahub", 42, "x")  # noqa: SLF001
    assert timeouts == [60, 60]
