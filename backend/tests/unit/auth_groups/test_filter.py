"""Unit tests for the ClaimFilter in `infrahub.auth_groups.filter`.

Covers the regex-based external-claim → effective-name derivation: first-match-per-claim
semantics, named-capture extraction, no-capture fallback to full-claim, positional captures
ignored for name extraction, and within-login dedup of effective names.
"""

from __future__ import annotations

import re

from infrahub.auth_groups.filter import ClaimFilter


def _compile(*patterns: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p) for p in patterns)


class TestNameForSingleClaim:
    """Semantics of `ClaimFilter.name_for()` applied to a single claim."""

    def test_named_capture_returns_captured_name(self) -> None:
        """A pattern with a `name` named capture group yields the captured value."""
        claim_filter = ClaimFilter(patterns=_compile(r"^LDAP/group/(?P<name>.+)$"))

        assert claim_filter.name_for("LDAP/group/network-engineering") == "network-engineering"

    def test_no_capture_returns_full_claim(self) -> None:
        """A pattern without a `name` named capture group yields the full claim string."""
        claim_filter = ClaimFilter(patterns=_compile(r"^network-.*$"))

        assert claim_filter.name_for("network-eng") == "network-eng"

    def test_no_capture_hierarchy_name_returns_full_claim(self) -> None:
        """A pattern without a `name` named capture group yields the full claim string."""
        claim_filter = ClaimFilter(patterns=_compile(r"^LDAP/group/*"))

        assert claim_filter.name_for("LDAP/group/network-engineering") == "LDAP/group/network-engineering"

    def test_non_matching_claim_returns_none(self) -> None:
        """Claims that match no pattern produce no effective name."""
        claim_filter = ClaimFilter(patterns=_compile(r"^LDAP/group/(?P<name>.+)$"))

        assert claim_filter.name_for("slack/general") is None

    def test_first_match_wins_when_multiple_patterns(self) -> None:
        """Patterns are tried in declared order; the first match per claim wins."""
        claim_filter = ClaimFilter(
            patterns=_compile(
                r"^LDAP/group/(?P<name>.+)$",
                r"^.*/(?P<name>[a-z]+)$",
            )
        )

        assert claim_filter.name_for("LDAP/group/network-engineering") == "network-engineering"

    def test_positional_capture_is_ignored_for_name_extraction(self) -> None:
        """Index-based capture groups are not used to derive the local name."""
        claim_filter = ClaimFilter(patterns=_compile(r"^LDAP/group/(.+)$"))

        assert claim_filter.name_for("LDAP/group/network-engineering") == "LDAP/group/network-engineering"

    def test_empty_patterns_means_feature_off(self) -> None:
        """No configured patterns deactivates the feature."""
        claim_filter = ClaimFilter(patterns=())

        assert claim_filter.is_active is False
        assert claim_filter.name_for("LDAP/group/network-engineering") is None


class TestNamesForManyClaims:
    """Semantics of `ClaimFilter.names_for()` applied to a list of claims."""

    def test_names_for_dedupes_effective_names(self) -> None:
        """Two claims resolving to the same effective name produce one entry."""
        claim_filter = ClaimFilter(patterns=_compile(r"^(?:LDAP|AD)/group/(?P<name>.+)$"))

        out = claim_filter.names_for(
            ["LDAP/group/network-engineering", "AD/group/network-engineering", "slack/general"]
        )

        assert out == ("network-engineering",)

    def test_names_for_preserves_order(self) -> None:
        """Effective names are returned in the order their claims first matched."""
        claim_filter = ClaimFilter(patterns=_compile(r"^LDAP/group/(?P<name>.+)$"))

        out = claim_filter.names_for(["LDAP/group/alpha", "LDAP/group/beta", "LDAP/group/gamma"])

        assert out == ("alpha", "beta", "gamma")
