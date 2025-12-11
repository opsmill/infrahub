import { Collection, ListBox, ListBoxLoadMoreItem } from "react-aria-components";

import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { useTitle } from "@/shared/hooks/useTitle";
import { sortByName } from "@/shared/utils/common";

import { useGetBranchesPaginated } from "@/entities/branches/domain/get-branches.query";
import { BranchListItem } from "@/entities/branches/ui/branch-list-item/branch-list-item";

export default function BranchesList() {
  useTitle("Branches list");
  const {
    data,
    refetch,
    isPending,
    error,
    isRefetching,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useGetBranchesPaginated();

  if (isPending) {
    return <InfrahubLoading>loading branches...</InfrahubLoading>;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const allBranches = data.pages.flat();
  const sortedBranches = sortByName(allBranches.filter((b) => b.name !== "main"));
  const branches = [...allBranches.filter((b) => b.name === "main"), ...sortedBranches];

  return (
    <Content.Card>
      <Content.CardTitle
        title="Branches"
        badgeContent={branches.length}
        isReloadLoading={isRefetching}
        reload={() => refetch()}
      />

      <ListBox
        aria-label="Branches list"
        className="m-2 flex flex-col divide-y rounded-lg border border-gray-200"
      >
        <Collection items={branches}>
          {(branch) => <BranchListItem branch={branch} />}
        </Collection>

        {hasNextPage && (
          <ListBoxLoadMoreItem isLoading={isFetchingNextPage} onLoadMore={fetchNextPage}>
            <LoadingIndicator />
          </ListBoxLoadMoreItem>
        )}
      </ListBox>
    </Content.Card>
  );
}
