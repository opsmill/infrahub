import { Collection, ListBox, ListBoxLoadMoreItem } from "react-aria-components";

import { queryClient } from "@/shared/api/rest/client";
import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { useSearch } from "@/shared/hooks/useSearch";
import { useTitle } from "@/shared/hooks/useTitle";
import { sortByName } from "@/shared/utils/common";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { useGetBranchesPaginated } from "@/entities/branches/domain/get-branches.query";
import { useGetBranchesCount } from "@/entities/branches/domain/get-branches-count.query";
import { BranchListItem } from "@/entities/branches/ui/branch-list-item/branch-list-item";
import { BranchesEmpty } from "@/entities/branches/ui/branches-empty";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";

function BranchesListHeader() {
  const [search] = useSearch();
  const { data: count, isPending, isRefetching, isError } = useGetBranchesCount(search);

  const refetchBranches = async () => {
    await queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all });
  };

  return (
    <Content.CardTitle
      title="Branches"
      badgeContent={isPending ? "..." : isError ? "-" : count}
      isReloadLoading={isRefetching}
      reload={refetchBranches}
    />
  );
}

function BranchesListToolbar() {
  return (
    <Col className="flex flex-col gap-2">
      <BranchesListHeader />

      <div className="max-w-56 px-3">
        <FilterSearchInput placeholder="Search branches" />
      </div>
    </Col>
  );
}

function BranchesListContent() {
  const [search] = useSearch();
  const { data, isPending, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useGetBranchesPaginated({ branchSearch: search });

  if (isPending) {
    return <LoadingIndicator className="py-8" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const allBranches = data.pages.flat();

  if (allBranches.length === 0) {
    return <BranchesEmpty />;
  }

  const sortedBranches = sortByName(allBranches.filter((b) => b.name !== "main"));
  const branches = [...allBranches.filter((b) => b.name === "main"), ...sortedBranches];

  return (
    <ListBox
      aria-label="Branches list"
      className="m-2 flex flex-col divide-y rounded-lg border border-gray-200"
    >
      <Collection items={branches}>{(branch) => <BranchListItem branch={branch} />}</Collection>

      {hasNextPage && (
        <ListBoxLoadMoreItem isLoading={isFetchingNextPage} onLoadMore={fetchNextPage}>
          <LoadingIndicator />
        </ListBoxLoadMoreItem>
      )}
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
