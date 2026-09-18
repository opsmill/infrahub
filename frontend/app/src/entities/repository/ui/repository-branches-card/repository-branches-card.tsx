import { Card, CardHeader } from "@infrahub/ui";
import { useId } from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { CELL_HEIGHT_PX } from "@/shared/components/table/style";
import { TablePagination } from "@/shared/components/table/table-pagination";
import { Badge } from "@/shared/components/ui/badge";
import { useTablePagination } from "@/shared/hooks/use-table-pagination";
import { formatNumberDisplay } from "@/shared/utils/number";
import { clampPage, getOffset, getTotalPages, PAGE_SIZE } from "@/shared/utils/table-pagination";

import { READONLY_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import {
  RepositoryBranchStatusError,
  type RepositoryBranchStatusPage,
} from "@/entities/repository/domain/model/repository-branch-status";
import { useGetRepositoryBranchStatus } from "@/entities/repository/ui/queries/get-repository-branch-status.query";
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
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

export const PAGINATION_URL_KEY = "branches";

interface RepositoryBranchesBodyProps {
  schema: ModelSchema;
  data: RepositoryBranchStatusPage | undefined;
  error: Error | null;
  isPending: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

function RepositoryBranchesBody({
  schema,
  data,
  error,
  isPending,
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
          // The card exposes no filter yet, so only a total of zero can mean there is nothing to show.
          renderEmpty={
            data.count === 0
              ? () => (
                  <RepositoryBranchesEmpty
                    hasFilters={false}
                    listsEveryBranch={isOfKind(READONLY_REPOSITORY_KIND, schema)}
                  />
                )
              : undefined
          }
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

export function RepositoryBranchesCard({ repositoryId, schema }: RepositoryBranchesCardProps) {
  const titleId = useId();
  const title = isOfKind(READONLY_REPOSITORY_KIND, schema)
    ? READ_ONLY_BRANCHES_TITLE
    : BRANCHES_TITLE;
  const { page, pageSize, offset, setPage } = useTablePagination({
    urlKey: PAGINATION_URL_KEY,
  });

  // The server's own total is the only thing that can say which page is the last real one, so a url
  // asking for a page past the end is answered once and then re-asked at the last page's offset.
  const requested = useGetRepositoryBranchStatus({ id: repositoryId, limit: pageSize, offset });
  const currentPage = requested.data
    ? clampPage(page, getTotalPages(requested.data.count, pageSize))
    : page;

  const { data, error, isPending } = useGetRepositoryBranchStatus({
    id: repositoryId,
    limit: pageSize,
    offset: getOffset(currentPage, pageSize),
  });

  return (
    <Card aria-labelledby={titleId} role="region">
      <CardHeader className="flex items-center gap-2">
        <h2 id={titleId}>{title}</h2>

        {data && (
          <Badge className="tabular-nums">
            {formatNumberDisplay(data.count)}{" "}
            <span className="sr-only">{data.count === 1 ? "branch" : "branches"}</span>
          </Badge>
        )}
      </CardHeader>

      <RepositoryBranchesCardBoundary resetKeys={[repositoryId, currentPage]}>
        <RepositoryBranchesBody
          data={data}
          error={error}
          isPending={isPending}
          onPageChange={setPage}
          page={currentPage}
          schema={schema}
        />
      </RepositoryBranchesCardBoundary>
    </Card>
  );
}
