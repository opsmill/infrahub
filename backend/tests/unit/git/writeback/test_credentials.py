from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.git.writeback.credentials import scrub_credentials


@dataclass
class ScrubCase:
    name: str
    text: str
    expected: str


SCRUB_CASES: list[ScrubCase] = [
    ScrubCase(
        name="user_and_token",
        text="fatal: unable to access 'https://admin:s3cret@gitlab.example.com/net/repo.git/'",
        expected="fatal: unable to access 'https://gitlab.example.com/net/repo.git/'",
    ),
    ScrubCase(
        name="user_alone",
        text="Cloning from https://deploy@gitlab.example.com/net/repo.git failed",
        expected="Cloning from https://gitlab.example.com/net/repo.git failed",
    ),
    ScrubCase(
        name="password_holding_an_at_sign",
        text="https://admin:p@ss@gitlab.example.com/net/repo.git",
        expected="https://gitlab.example.com/net/repo.git",
    ),
    ScrubCase(
        name="several_urls_in_one_text",
        text=(
            "remote: mirrored from https://ci:t0ken@one.example.com/a.git to http://bot@two.example.com:8080/b.git\n"
            "remote: and ssh://git@three.example.com/c.git"
        ),
        expected=(
            "remote: mirrored from https://one.example.com/a.git to http://two.example.com:8080/b.git\n"
            "remote: and ssh://three.example.com/c.git"
        ),
    ),
    ScrubCase(
        name="url_right_after_an_underscore",
        text="loc=_https://u:tok@h",
        expected="loc=_https://h",
    ),
    ScrubCase(
        name="url_right_after_a_digit",
        text="1https://u:tok@h",
        expected="1https://h",
    ),
    ScrubCase(
        name="password_holding_a_slash",
        text="fatal: unable to access 'https://admin:p/ss@gitlab.example.com/net/repo.git/'",
        expected="fatal: unable to access 'https://gitlab.example.com/net/repo.git/'",
    ),
    ScrubCase(
        name="password_holding_a_hash",
        text="https://admin:p#ss@gitlab.example.com/net/repo.git",
        expected="https://gitlab.example.com/net/repo.git",
    ),
    ScrubCase(
        name="password_holding_a_question_mark",
        text="https://admin:p?ss@gitlab.example.com/net/repo.git",
        expected="https://gitlab.example.com/net/repo.git",
    ),
    ScrubCase(
        name="password_holding_a_single_quote",
        text="https://admin:pa'ss@gitlab.example.com/net/repo.git",
        expected="https://gitlab.example.com/net/repo.git",
    ),
    ScrubCase(
        name="password_holding_a_single_quote_in_a_quoted_url",
        text="fatal: unable to access 'https://admin:pa'ss@gitlab.example.com/net/repo.git/': 403",
        expected="fatal: unable to access 'https://gitlab.example.com/net/repo.git/': 403",
    ),
    ScrubCase(
        name="url_in_double_quotes_ends_at_the_quote",
        text='{"location": "https://admin:s3cret@gitlab.example.com/net/repo.git","owner":"admin@example.com"}',
        expected='{"location": "https://gitlab.example.com/net/repo.git","owner":"admin@example.com"}',
    ),
    ScrubCase(
        name="at_sign_in_the_path_removes_what_comes_before_it",
        text="Ask admin@example.com about https://gitlab.example.com:8443/team@infra/repo.git now",
        expected="Ask admin@example.com about https://infra/repo.git now",
    ),
    ScrubCase(
        name="text_with_no_credentials_stays_as_it_is",
        text="Ask admin@example.com about https://gitlab.example.com:8443/infra/repo.git?ref=main",
        expected="Ask admin@example.com about https://gitlab.example.com:8443/infra/repo.git?ref=main",
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SCRUB_CASES])
def test_scrub_credentials(case: ScrubCase) -> None:
    assert scrub_credentials(text=case.text) == case.expected
