import { ListBox } from "react-aria-components";

import { queryClient } from "@/shared/api/rest/client";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { useSearch } from "@/shared/hooks/useSearch";
import { useTitle } from "@/shared/hooks/useTitle";
import { sortByName } from "@/shared/utils/common";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { useGetBranches, useGetBranchesCount } from "@/entities/branches/domain/get-branches.query";
import { BranchListItem } from "@/entities/branches/ui/branch-list-item/branch-list-item";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";

function BranchesListHeader() {
  const [search] = useSearch();
  const {
    data: count,
    isPending,
    isRefetching,
    isError,
  } = useGetBranchesCount(search || undefined);

  const refetchBranches = async () => {
    await queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
  };

  return (
    <Content.CardTitle
      title="Branches"
      badgeContent={isPending && !isError ? "..." : count}
      isReloadLoading={isRefetching}
      reload={refetchBranches}
    />
  );
}

function BranchesListToolbar() {
  return (
    <div className="flex flex-col gap-2">
      <BranchesListHeader />

      <div className="max-w-56 px-3">
        <FilterSearchInput placeholder="Search branches" />
      </div>
    </div>
  );
}

function BranchesListContent() {
  const [search] = useSearch();
  const { data: storedBranches, isPending, error } = useGetBranches(search || undefined);

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const sortedBranches = sortByName(storedBranches.filter((b) => b.name !== "main"));
  const branches = [...storedBranches.filter((b) => b.name === "main"), ...sortedBranches];

  return (
    <ListBox
      aria-label="Branches list"
      items={branches}
      className="m-2 flex flex-col divide-y rounded-lg border border-gray-200"
    >
      {(branch) => <BranchListItem branch={branch} />}
    </ListBox>
  );
}

export default function BranchesList() {
  useTitle("Branches list");

  return (
    <Content.Card>
      <BranchesListToolbar />
      <BranchesListContent />
    </Content.Card>
  );
}
