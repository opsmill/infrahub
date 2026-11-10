import { useQueryClient } from "@tanstack/react-query";
import React from "react";

import { Col, Row } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import { BRANCH_FILTER_DEFINITIONS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import { BranchesTable } from "@/entities/branches/ui/branches-table/branches-table";
import {
  useGitStatusRefreshTaskIdFromNavigation,
  useRefreshBranchGitStatusOnTaskEnd,
} from "@/entities/branches/ui/hooks/use-refresh-branch-git-status-on-task-end";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { useGetBranchesCount } from "@/entities/branches/ui/queries/get-branches-count.query";
import { ActiveFilterTags } from "@/entities/nodes/filters/ui/active-filter-tags";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";

function BranchesListHeader() {
  const [filters] = useFilters();
  const { data: count, isPending, isRefetching, isError } = useGetBranchesCount(filters);
  const [isReloading, setIsReloading] = React.useState(false);
  const queryClient = useQueryClient();

  const reload = async () => {
    setIsReloading(true);
    try {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: branchesQueryKeys.all }),
        queryClient.invalidateQueries({ queryKey: branchGitStatusQueryKeys.all }),
      ]);
    } finally {
      setIsReloading(false);
    }
  };

  return (
    <Content.CardTitle
      title="Branches"
      badgeContent={isPending ? "..." : isError ? "-" : count}
      isReloadLoading={isRefetching || isReloading}
      reload={reload}
    />
  );
}

function BranchesListToolbar() {
  const [filters, setFilters] = useFilters();

  return (
    <Col className="gap-0">
      <BranchesListHeader />

      <Row className="px-3 py-2">
        <FilterSearchInput placeholder="Search branches" />

        <ActiveFilterTags
          filters={filters}
          setFilters={setFilters}
          filterDefinitions={BRANCH_FILTER_DEFINITIONS}
          className="p-0"
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
  useRefreshBranchGitStatusOnTaskEnd(useGitStatusRefreshTaskIdFromNavigation());

  return (
    <Content.Card>
      <BranchesListToolbar />
      <BranchesListContent />
    </Content.Card>
  );
}
