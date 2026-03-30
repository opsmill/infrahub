import { queryClient } from "@/shared/api/rest/client";
import { Col, Row } from "@/shared/components/container";
import { ActiveFilterTags } from "@/shared/components/filters/active-filter-tags";
import Content from "@/shared/components/layout/content";
import useFilters from "@/shared/hooks/useFilters";
import { useTitle } from "@/shared/hooks/useTitle";

import { BRANCH_FIELD_SCHEMAS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import { BranchesTable } from "@/entities/branches/ui/branches-table/branches-table";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { useGetBranchesCount } from "@/entities/branches/ui/queries/get-branches-count.query";
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
  const [filters, setFilters] = useFilters();

  return (
    <Col className="gap-0">
      <BranchesListHeader />

      <Row className="items-center gap-2 px-3">
        <div className="max-w-56 py-3">
          <FilterSearchInput placeholder="Search branches" />
        </div>
        <ActiveFilterTags
          filters={filters}
          setFilters={setFilters}
          fieldSchemas={BRANCH_FIELD_SCHEMAS}
        />
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
