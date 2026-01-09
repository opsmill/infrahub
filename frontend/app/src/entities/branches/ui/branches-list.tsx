import { queryClient } from "@/shared/api/rest/client";
import { Col } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { useSearch } from "@/shared/hooks/useSearch";
import { useTitle } from "@/shared/hooks/useTitle";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { useGetBranchesCount } from "@/entities/branches/domain/get-branches-count.query";
import { BranchesTable } from "@/entities/branches/ui/branches-table/branches-table";
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
    <Col className="gap-0">
      <BranchesListHeader />

      <div className="max-w-56 p-3">
        <FilterSearchInput placeholder="Search branches" />
      </div>
    </Col>
  );
}

function BranchesListContent() {
  const [search] = useSearch();

  return <BranchesTable search={search} />;
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
