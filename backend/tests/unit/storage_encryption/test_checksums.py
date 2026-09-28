from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.storage_encryption.checksums import matches_recorded_checksum


@dataclass
class ChecksumCase:
    name: str
    checksums: frozenset[str]
    expected: bool | None


# MD5 and SHA-1 digests of b"interface Ethernet1", computed with coreutils md5sum and sha1sum.
CHECKSUM_CASES = [
    ChecksumCase(name="md5_match", checksums=frozenset({"ba30967742eca9881154761d839689f0"}), expected=True),
    ChecksumCase(name="sha1_match", checksums=frozenset({"2e9ad9785351f3817800eab7132d19f946674350"}), expected=True),
    ChecksumCase(
        name="uppercase_digest_match", checksums=frozenset({"BA30967742ECA9881154761D839689F0"}), expected=True
    ),
    ChecksumCase(
        name="one_of_several_matches",
        checksums=frozenset({"0" * 32, "ba30967742eca9881154761d839689f0"}),
        expected=True,
    ),
    ChecksumCase(name="md5_mismatch", checksums=frozenset({"ba30967742eca9881154761d839689f1"}), expected=False),
    ChecksumCase(name="sha1_mismatch", checksums=frozenset({"0" * 40}), expected=False),
    ChecksumCase(name="nothing_recorded", checksums=frozenset(), expected=None),
    ChecksumCase(name="digest_of_an_unknown_algorithm", checksums=frozenset({"abc123"}), expected=None),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in CHECKSUM_CASES])
def test_content_is_compared_with_the_checksums_recorded_for_it(case: ChecksumCase) -> None:
    assert matches_recorded_checksum(content=b"interface Ethernet1", checksums=case.checksums) is case.expected
