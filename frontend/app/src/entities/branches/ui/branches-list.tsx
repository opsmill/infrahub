import { queryClient } from "@/shared/api/rest/client";
import { Col, Row } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import useFilters from "@/shared/hooks/useFilters";
import { useTitle } from "@/shared/hooks/useTitle";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { useGetBranchesCount } from "@/entities/branches/domain/get-branches-count.query";
import { ActiveBranchFilterTags } from "@/entities/branches/ui/filters/active-branch-filter-tags";
import { BranchesTable } from "@/entities/branches/ui/branches-table/branches-table";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";

function BranchesListHeader() {
  const [filters] = useFilters();
  const { data: count, isPending, isRefetching, isError } = useGetBranchesCount(filters);

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

      <Row className="items-center gap-2 px-3">
        <div className="max-w-56 py-3">
          <FilterSearchInput placeholder="Search branches" />
        </div>
        <ActiveBranchFilterTags />
      </Row>
    </Col>
  );
}

function BranchesListContent() {
  return <BranchesTable />;
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
