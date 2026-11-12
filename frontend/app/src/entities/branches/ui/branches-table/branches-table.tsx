import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { sortByName } from "@/shared/utils/common";

import { useGetBranchGitStatuses } from "@/entities/branch-git-status/ui/hooks/use-get-branch-git-statuses";
import { BranchesEmpty } from "@/entities/branches/ui/branches-empty";
import { toBranchTableRows } from "@/entities/branches/ui/branches-table/branch-table-row";
import { BranchesDataTable } from "@/entities/branches/ui/branches-table/branches-data-table";
import { getBranchTableColumns } from "@/entities/branches/ui/branches-table/get-branch-table-columns";
import { useGetBranchesPaginated } from "@/entities/branches/ui/queries/get-branches.query";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";

export function BranchesTable() {
  const [filters] = useFilters();

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } =
    useGetBranchesPaginated({ filters });

  const columns = getBranchTableColumns();

  const allBranches = data?.pages.flat() ?? [];
  const otherBranches = sortByName(allBranches.filter((b) => !b.is_default));
  const branches = [...allBranches.filter((b) => b.is_default), ...otherBranches];

  const gitStatuses = useGetBranchGitStatuses(branches.map((branch) => branch.name));
  const rows = toBranchTableRows(branches, gitStatuses);

  const isLoading = isPending || isFetchingNextPage;

  return (
    <InfiniteScroll
      scrollX
      className="bg-table-frame"
      hasNextPage={hasNextPage}
      onLoadMore={fetchNextPage}
    >
      <BranchesDataTable
        columns={columns}
        data={rows}
        isLoading={isLoading}
        renderEmpty={() => <BranchesEmpty />}
        data-testid="branches-table"
      />
    </InfiniteScroll>
  );
}
