import { Card, CardHeader } from "@infrahub/ui";
import { useEffect, useId } from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { CELL_HEIGHT_PX } from "@/shared/components/table/style";
import { TablePagination } from "@/shared/components/table/table-pagination";
import { Badge } from "@/shared/components/ui/badge";
import { useTablePagination } from "@/shared/hooks/use-table-pagination";
import { formatNumberDisplay } from "@/shared/utils/number";
import { clampPage, getTotalPages, PAGE_SIZE } from "@/shared/utils/table-pagination";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { FilterScopeProvider } from "@/entities/nodes/filters/ui/filter-scope-context";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import { READONLY_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import {
  RepositoryBranchStatusError,
  type RepositoryBranchStatusPage,
} from "@/entities/repository/domain/model/repository-branch-status";
import { useGetRepositoryBranchStatus } from "@/entities/repository/ui/queries/get-repository-branch-status.query";
import { BRANCH_ROW_SORT_SCHEMA } from "@/entities/repository/ui/repository-branches-card/branch-row-fields";
import {
  branchesGridTemplateColumns,
  getRepositoryBranchesColumns,
} from "@/entities/repository/ui/repository-branches-card/columns";
import {
  BRANCHES_LOAD_FAILED,
  BRANCHES_PERMISSION_DENIED,
  BRANCHES_TITLE,
  READ_ONLY_BRANCHES_TITLE,
} from "@/entities/repository/ui/repository-branches-card/messages";
import { RepositoryBranchesCardBoundary } from "@/entities/repository/ui/repository-branches-card/repository-branches-card-boundary";
import { RepositoryBranchesEmpty } from "@/entities/repository/ui/repository-branches-card/repository-branches-empty";
import { RepositoryBranchesToolbar } from "@/entities/repository/ui/repository-branches-card/repository-branches-toolbar";
import {
  hasRepositoryBranchFilters,
  toRepositoryBranchArguments,
} from "@/entities/repository/ui/repository-branches-card/to-repository-branch-arguments";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

/** Scopes this card's page, filters and order so no other table can read or overwrite them. */
export const BRANCHES_URL_KEY = "branches";

interface RepositoryBranchesBodyProps {
  schema: ModelSchema;
  data: RepositoryBranchStatusPage | undefined;
  error: Error | null;
  isPending: boolean;
  hasFilters: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

function RepositoryBranchesBody({
  schema,
  data,
  error,
  isPending,
  hasFilters,
  page,
  onPageChange,
}: RepositoryBranchesBodyProps) {
  if (error) {
    if (error instanceof RepositoryBranchStatusError && error.code === "PERMISSION_DENIED") {
      return (
        <UnauthorizedScreen
          className="flex-none py-12"
          defaultOpen
          message={BRANCHES_PERMISSION_DENIED}
        />
      );
    }

    return <ErrorScreen className="flex-none py-12" message={BRANCHES_LOAD_FAILED} />;
  }

  const columns = getRepositoryBranchesColumns(schema);

  if (isPending || !data) {
    return (
      <div className="overflow-x-auto">
        <DataTable
          columns={columns}
          data={[]}
          gridTemplateColumns={branchesGridTemplateColumns}
          isLoading
          semanticTable
          skeletonRowCount={PAGE_SIZE}
          skeletonShowSelection={false}
        />
      </div>
    );
  }

  // A short last page would otherwise shrink the card and move everything below it.
  const hasMultiplePages = data.count > PAGE_SIZE;

  return (
    <>
      <div
        className="overflow-x-auto"
        style={hasMultiplePages ? { minHeight: (PAGE_SIZE + 1) * CELL_HEIGHT_PX } : undefined}
      >
        <DataTable
          columns={columns}
          data={data.rows}
          gridTemplateColumns={branchesGridTemplateColumns}
          renderEmpty={() => (
            <RepositoryBranchesEmpty
              hasFilters={hasFilters}
              isPagePastTheEnd={data.count > 0}
              listsEveryBranch={isOfKind(READONLY_REPOSITORY_KIND, schema)}
            />
          )}
          semanticTable
        />
      </div>

      {data.count > 0 && (
        <TablePagination
          onPageChange={onPageChange}
          page={page}
          pageSize={PAGE_SIZE}
          totalCount={data.count}
        />
      )}
    </>
  );
}

interface RepositoryBranchesCardProps {
  repositoryId: string;
  schema: ModelSchema;
}

function RepositoryBranchesCardInScope({ repositoryId, schema }: RepositoryBranchesCardProps) {
  const titleId = useId();
  const title = isOfKind(READONLY_REPOSITORY_KIND, schema)
    ? READ_ONLY_BRANCHES_TITLE
    : BRANCHES_TITLE;
  const { page, setPage, pageSize, offset } = useTablePagination({ urlKey: BRANCHES_URL_KEY });
  const [filters] = useFilters();
  const { appliedSort } = useSort(BRANCH_ROW_SORT_SCHEMA);

  const queryArguments = toRepositoryBranchArguments(filters, appliedSort);
  const querySignature = JSON.stringify(queryArguments);

  const { currentBranch } = useCurrentBranch();
  const { data, error, isPending, isPlaceholderData } = useGetRepositoryBranchStatus({
    id: repositoryId,
    limit: pageSize,
    offset,
    ...queryArguments,
  });

  // Only a count answering the current request can say which page is the last real one, so a url
  // asking past the end is corrected once the server replies rather than guessed at.
  const canClamp = data !== undefined && !isPlaceholderData;
  const currentPage = canClamp ? clampPage(page, getTotalPages(data.count, pageSize)) : page;

  useEffect(() => {
    if (currentPage === page) return;

    setPage(currentPage);
  }, [currentPage, page]);

  return (
    <Card aria-labelledby={titleId} role="region">
      <CardHeader className="flex flex-wrap items-center gap-2">
        <h2 id={titleId}>{title}</h2>

        {data && (
          <Badge className="tabular-nums">
            {formatNumberDisplay(data.count)}{" "}
            <span className="sr-only">{data.count === 1 ? "branch" : "branches"}</span>
          </Badge>
        )}
      </CardHeader>

      <RepositoryBranchesToolbar />

      <RepositoryBranchesCardBoundary
        resetKeys={[repositoryId, currentBranch.name, currentPage, querySignature]}
      >
        <RepositoryBranchesBody
          data={data}
          error={error}
          hasFilters={hasRepositoryBranchFilters(filters)}
          isPending={isPending}
          onPageChange={setPage}
          page={currentPage}
          schema={schema}
        />
      </RepositoryBranchesCardBoundary>
    </Card>
  );
}

export function RepositoryBranchesCard(props: RepositoryBranchesCardProps) {
  return (
    <FilterScopeProvider urlKey={BRANCHES_URL_KEY}>
      <RepositoryBranchesCardInScope {...props} />
    </FilterScopeProvider>
  );
}
