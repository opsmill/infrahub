from unittest.mock import MagicMock

import pytest

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.graphql.middleware import raise_on_mutation_for_branch_status


class TestMiddlewareMergedBranch:
    def test_middleware_blocks_mutation_on_merged_branch(self) -> None:
        mock_info = MagicMock()
        mock_info.operation.operation.value = "mutation"
        mock_info.operation.selection_set.selections[0].name.value = "TestingPersonCreate"
        mock_info.context.branch = Branch(name="merged-branch", status=BranchStatus.MERGED)

        mock_next = MagicMock()

        with pytest.raises(ValueError, match=r"merged-branch.*has been merged and is read-only"):
            raise_on_mutation_for_branch_status(mock_next, None, mock_info)

    def test_middleware_allows_branch_delete_on_merged_branch(self) -> None:
        mock_info = MagicMock()
        mock_info.operation.operation.value = "mutation"
        mock_info.operation.selection_set.selections[0].name.value = "BranchDelete"
        mock_info.context.branch = Branch(name="merged-branch", status=BranchStatus.MERGED)

        mock_next = MagicMock(return_value="result")

        result = raise_on_mutation_for_branch_status(mock_next, None, mock_info)

        mock_next.assert_called_once_with(None, mock_info)
        assert result == "result"

    def test_middleware_allows_query_on_merged_branch(self) -> None:
        mock_info = MagicMock()
        mock_info.operation.operation.value = "query"
        mock_info.context.branch = Branch(name="merged-branch", status=BranchStatus.MERGED)

        mock_next = MagicMock(return_value="result")

        result = raise_on_mutation_for_branch_status(mock_next, None, mock_info)

        mock_next.assert_called_once_with(None, mock_info)
        assert result == "result"

    def test_middleware_allows_mutation_on_open_branch(self) -> None:
        mock_info = MagicMock()
        mock_info.operation.operation.value = "mutation"
        mock_info.operation.selection_set.selections[0].name.value = "TestingPersonCreate"
        mock_info.context.branch = Branch(name="open-branch", status=BranchStatus.OPEN)

        mock_next = MagicMock(return_value="result")

        result = raise_on_mutation_for_branch_status(mock_next, None, mock_info)

        mock_next.assert_called_once()
        assert result == "result"
