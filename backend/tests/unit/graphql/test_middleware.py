from unittest.mock import MagicMock

import pytest

from infrahub.core.branch.enums import BranchStatus
from infrahub.graphql.middleware import raise_on_mutation_on_branch_needing_rebase


class TestMiddlewareMergedBranch:
    def test_middleware_blocks_mutation_on_merged_branch(self) -> None:
        mock_branch = MagicMock()
        mock_branch.status = BranchStatus.MERGED
        mock_branch.name = "merged-branch"

        mock_info = MagicMock()
        mock_info.operation.operation.value = "mutation"
        mock_info.operation.selection_set.selections[0].name.value = "TestingPersonCreate"
        mock_info.context.branch = mock_branch

        mock_next = MagicMock()

        with pytest.raises(ValueError, match=r"merged-branch.*has been merged and is read-only"):
            raise_on_mutation_on_branch_needing_rebase(mock_next, None, mock_info)

    def test_middleware_allows_branch_delete_on_merged_branch(self) -> None:
        mock_branch = MagicMock()
        mock_branch.status = BranchStatus.MERGED
        mock_branch.name = "merged-branch"

        mock_info = MagicMock()
        mock_info.operation.operation.value = "mutation"
        mock_info.operation.selection_set.selections[0].name.value = "BranchDelete"
        mock_info.context.branch = mock_branch

        mock_next = MagicMock(return_value="result")

        result = raise_on_mutation_on_branch_needing_rebase(mock_next, None, mock_info)

        mock_next.assert_called_once_with(None, mock_info)
        assert result == "result"

    def test_middleware_allows_query_on_merged_branch(self) -> None:
        mock_branch = MagicMock()
        mock_branch.status = BranchStatus.MERGED
        mock_branch.name = "merged-branch"

        mock_info = MagicMock()
        mock_info.operation.operation.value = "query"
        mock_info.context.branch = mock_branch

        mock_next = MagicMock(return_value="result")

        result = raise_on_mutation_on_branch_needing_rebase(mock_next, None, mock_info)

        mock_next.assert_called_once_with(None, mock_info)
        assert result == "result"

    def test_middleware_allows_mutation_on_open_branch(self) -> None:
        mock_branch = MagicMock()
        mock_branch.status = BranchStatus.OPEN
        mock_branch.name = "open-branch"

        mock_info = MagicMock()
        mock_info.operation.operation.value = "mutation"
        mock_info.operation.selection_set.selections[0].name.value = "TestingPersonCreate"
        mock_info.context.branch = mock_branch

        mock_next = MagicMock(return_value="result")

        result = raise_on_mutation_on_branch_needing_rebase(mock_next, None, mock_info)

        mock_next.assert_called_once()
        assert result == "result"
