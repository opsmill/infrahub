"""Deliberately failing test used to exercise CI on a test PR.

This file is intentional: it forces the backend unit test job to fail so we
can validate the CI / PR workflow. Delete this file (and the PR) once done.
"""

import pytest


def test_ci_intentional_failure() -> None:
    # Intentional failure to make the backend test job go red.
    pytest.fail("intentional CI failure for test PR")
