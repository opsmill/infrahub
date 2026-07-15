"""Tests for (un)pickling errors.

Prefect rebuilds errors using pickle.
"""

import pickle  # noqa: S403
from dataclasses import dataclass

import pytest

from infrahub.exceptions import (
    CommitNotFoundError,
    Error,
    GraphQLQueryError,
    PropagatedFromWorkerError,
    RepositoryFileNotFoundError,
    RepositoryInvalidBranchError,
    RPCError,
    SchemaNotFoundError,
)


def _round_trip(error: Error) -> Error:
    return pickle.loads(pickle.dumps(error))  # noqa: S301


@dataclass
class ErrorPickleCase:
    name: str
    error: Error


ERROR_PICKLE_CASES = [
    ErrorPickleCase(
        name="required_kwargs_beyond_message",
        error=SchemaNotFoundError(branch_name="main", identifier="TestingReproSolo"),
    ),
    ErrorPickleCase(
        name="explicit_message_override",
        error=SchemaNotFoundError(branch_name="dev", identifier="CoreNode", message="custom message"),
    ),
    ErrorPickleCase(
        name="multiple_required_positional_args",
        error=RepositoryInvalidBranchError(identifier="repo-1", branch_name="feature", location="/repos/repo-1"),
    ),
    ErrorPickleCase(
        name="repository_file_not_found",
        error=RepositoryFileNotFoundError(repository_name="repo-1", location="/config.yml", commit="abc123"),
    ),
    ErrorPickleCase(
        name="commit_not_found",
        error=CommitNotFoundError(identifier="repo-1", commit="deadbeef"),
    ),
    ErrorPickleCase(
        name="instance_http_code_no_super_init",
        error=PropagatedFromWorkerError(http_code=503, message="worker unavailable"),
    ),
    ErrorPickleCase(
        name="single_message_arg",
        error=RPCError(message="rpc failed"),
    ),
    ErrorPickleCase(
        name="list_arg",
        error=GraphQLQueryError(errors=[{"message": "bad query"}]),
    ),
]


@pytest.mark.parametrize("case", ERROR_PICKLE_CASES, ids=lambda case: case.name)
def test_error_pickle_round_trip(case: ErrorPickleCase) -> None:
    """Every Error subclass round-trips through pickle regardless of signature."""
    restored = _round_trip(case.error)

    assert type(restored) is type(case.error)
    assert restored.__dict__ == case.error.__dict__
    assert restored.args == case.error.args
    assert str(restored) == str(case.error)
    assert restored.HTTP_CODE == case.error.HTTP_CODE


def test_pickle_preserves_extra_constructor_attributes() -> None:
    error = SchemaNotFoundError(branch_name="main", identifier="TestingReproSolo")

    restored = _round_trip(error)

    assert isinstance(restored, SchemaNotFoundError)
    assert restored.branch_name == "main"
    assert restored.identifier == "TestingReproSolo"


def test_reconstructed_error_can_be_raised_and_caught() -> None:
    error = SchemaNotFoundError(branch_name="main", identifier="CoreNode")

    restored = _round_trip(error)

    with pytest.raises(SchemaNotFoundError, match=r"Unable to find the schema CoreNode in the database\."):
        raise restored
