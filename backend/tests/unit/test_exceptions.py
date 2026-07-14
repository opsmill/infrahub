import pickle  # noqa: S403

from infrahub.exceptions import SchemaNotFoundError


def test_schema_not_found_error_is_picklable() -> None:
    """SchemaNotFoundError must survive a pickle round-trip.

    It is transported across process boundaries (e.g. by Prefect); if it cannot be
    unpickled, the real error is masked by a TypeError from its own constructor.
    """
    error = SchemaNotFoundError(branch_name="main", identifier="TestingWidget")

    restored = pickle.loads(pickle.dumps(error))  # noqa: S301

    assert isinstance(restored, SchemaNotFoundError)
    assert restored.branch_name == error.branch_name
    assert restored.identifier == error.identifier
    assert restored.message == error.message
    assert str(restored) == str(error)
