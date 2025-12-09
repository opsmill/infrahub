import pytest
from infrahub_sdk.exceptions import TimestampFormatError
from pydantic import ValidationError

from infrahub.api.diff.validation_models import DiffQueryValidated
from infrahub.core.branch import Branch


class TestDiffQueryValidation:
    def setup_method(self) -> None:
        self.branch = Branch(name="abc")
        self.time_start_str = "2023-06-11"
        self.time_end_str = "2023-06-13"

    def test_valid_query(self) -> None:
        query = DiffQueryValidated(
            branch=self.branch, time_from=self.time_start_str, time_to=self.time_end_str, branch_only=True
        )

        assert query.branch == self.branch
        assert query.time_from == self.time_start_str
        assert query.time_to == self.time_end_str
        assert query.branch_only is True

    def test_invalid_time_from(self) -> None:
        with pytest.raises(TimestampFormatError):
            DiffQueryValidated(branch=self.branch, time_from="notatime")

    def test_invalid_time_to(self) -> None:
        with pytest.raises(TimestampFormatError):
            DiffQueryValidated(branch=self.branch, time_to="notatime")

    def test_invalid_time_range(self) -> None:
        with pytest.raises(ValidationError, match="time_from and time_to are not a valid time range"):
            DiffQueryValidated(
                branch=self.branch, time_from=self.time_end_str, time_to=self.time_start_str, branch_only=True
            )

    def test_time_from_required_for_default_branch(self) -> None:
        self.branch.is_default = True

        with pytest.raises(ValidationError, match=r"time_from is mandatory when diffing on the default branch `abc`."):
            DiffQueryValidated(branch=self.branch, branch_only=True)
