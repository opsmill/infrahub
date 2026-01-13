import React from "react";

import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { sortByName } from "@/shared/utils/common";

import { useGetBranchesPaginated } from "@/entities/branches/domain/get-branches.query";
import { BranchesEmpty } from "@/entities/branches/ui/branches-empty";
import { BranchesDataTable } from "@/entities/branches/ui/branches-table/branches-data-table";
import { getBranchTableColumns } from "@/entities/branches/ui/branches-table/get-branch-table-columns";

interface BranchesTableProps {
  search?: string;
}

export function BranchesTable({ search }: BranchesTableProps) {
  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } =
    useGetBranchesPaginated({ branchSearch: search });

  const columns = React.useMemo(() => getBranchTableColumns(), []);

  const flatData = React.useMemo(() => {
    if (!data?.pages) return [];

    const allBranches = data.pages.flat();
    const sortedBranches = sortByName(allBranches.filter((b) => b.name !== "main"));
    const branches = [...allBranches.filter((b) => b.name === "main"), ...sortedBranches];

    return branches;
  }, [data]);

  const isLoading = isPending || isFetchingNextPage;

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <BranchesDataTable
        columns={columns}
        data={flatData}
        isLoading={isLoading}
        renderEmpty={() => <BranchesEmpty />}
        data-testid="branches-table"
      />
    </InfiniteScroll>
  );
}
