import { Card, CardHeader } from "@infrahub/ui";
import { useId } from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { TablePagination } from "@/shared/components/table/table-pagination";
import { Badge } from "@/shared/components/ui/badge";
import { useTablePagination } from "@/shared/hooks/use-table-pagination";
import { formatNumberDisplay } from "@/shared/utils/number";

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

const PAGINATION_URL_KEY = "branches";

interface RepositoryBranchesBodyProps {
  schema: ModelSchema;
  data: RepositoryBranchStatusPage | undefined;
  error: Error | null;
  isPending: boolean;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

function RepositoryBranchesBody({
  schema,
  data,
  error,
  isPending,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
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
          skeletonRowCount={pageSize}
          skeletonShowSelection={false}
        />
      </div>
    );
  }

  return (
    <>
      <div className="overflow-x-auto">
        <DataTable
          columns={columns}
          data={data.rows}
          gridTemplateColumns={branchesGridTemplateColumns}
          // The card exposes no filter yet, so an empty result can only mean the repository has no
          // branch in scope.
          renderEmpty={() => <RepositoryBranchesEmpty hasFilters={false} />}
        />
      </div>

      {data.rows.length > 0 && (
        <TablePagination
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
          page={page}
          pageSize={pageSize}
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
  const { page, pageSize, offset, setPage, setPageSize } = useTablePagination({
    urlKey: PAGINATION_URL_KEY,
  });

  const { data, error, isPending } = useGetRepositoryBranchStatus({
    id: repositoryId,
    limit: pageSize,
    offset,
  });

  return (
    <Card aria-labelledby={titleId} role="region">
      <CardHeader className="flex items-center gap-2">
        <h2 id={titleId}>{title}</h2>

        {data && (
          <Badge aria-label={`${data.count} branches`} role="status">
            {formatNumberDisplay(data.count)}
          </Badge>
        )}
      </CardHeader>

      <RepositoryBranchesCardBoundary>
        <RepositoryBranchesBody
          data={data}
          error={error}
          isPending={isPending}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
          page={page}
          pageSize={pageSize}
          schema={schema}
        />
      </RepositoryBranchesCardBoundary>
    </Card>
  );
}
