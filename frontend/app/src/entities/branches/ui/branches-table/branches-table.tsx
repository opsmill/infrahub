import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { sortByName } from "@/shared/utils/common";

import { BranchesEmpty } from "@/entities/branches/ui/branches-empty";
import { BranchesDataTable } from "@/entities/branches/ui/branches-table/branches-data-table";
import { getBranchTableColumns } from "@/entities/branches/ui/branches-table/get-branch-table-columns";
import { useBranchTableRows } from "@/entities/branches/ui/hooks/use-branch-table-rows";
import { useGetBranchesPaginated } from "@/entities/branches/ui/queries/get-branches.query";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";

export function BranchesTable() {
  const [filters] = useFilters();

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } =
    useGetBranchesPaginated({ filters });

  const columns = getBranchTableColumns();

  const allBranches = data?.pages.flat() ?? [];
  const sortedBranches = sortByName(allBranches.filter((b) => !b.is_default));
  const flatData = [...allBranches.filter((b) => b.is_default), ...sortedBranches];

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
        data={useBranchTableRows(flatData)}
        isLoading={isLoading}
        renderEmpty={() => <BranchesEmpty />}
        data-testid="branches-table"
      />
    </InfiniteScroll>
  );
}
