import { Card, CardHeader } from "@infrahub/ui";

import { CELL_HEIGHT_PX } from "@/shared/components/table/style";
import { TablePagination } from "@/shared/components/table/table-pagination";
import { Badge } from "@/shared/components/ui/badge";
import { useTablePagination } from "@/shared/hooks/use-table-pagination";
import { PAGE_SIZE } from "@/shared/utils/table-pagination";

import {
  BranchRepositoriesError,
  type BranchRepositoryPage,
} from "@/entities/repository/domain/model/branch-repository";
import { isAnyRepositorySyncing } from "@/entities/repository/domain/rules/is-any-repository-syncing";
import {
  countUnlistedFailures,
  getFailingRepositories,
} from "@/entities/repository/domain/rules/repository-failures";
import {
  BranchRepositoriesDenied,
  BranchRepositoriesFailed,
  BranchRepositoriesLoading,
  BranchRepositoriesNone,
  BranchRepositoriesNotSynced,
  BranchRepositoryHealthFailed,
} from "@/entities/repository/ui/branch-repositories/branch-repositories-states";
import { BranchRepositoriesTable } from "@/entities/repository/ui/branch-repositories/branch-repositories-table";
import { RepositoryErrorBands } from "@/entities/repository/ui/branch-repositories/repository-error-bands";
import { useGetBranchRepositories } from "@/entities/repository/ui/queries/get-branch-repositories.query";
import { useGetBranchRepositoryHealth } from "@/entities/repository/ui/queries/get-branch-repository-health.query";

export const REPOSITORIES_URL_KEY = "repositories";

interface BranchRepositoriesCardProps {
  branchName: string;
  syncWithGit: boolean;
}

export function BranchRepositoriesCard({ branchName, syncWithGit }: BranchRepositoriesCardProps) {
  const { page, setPage, pageSize } = useTablePagination({ urlKey: REPOSITORIES_URL_KEY });
  const { data: health, isError: isHealthError } = useGetBranchRepositoryHealth({
    branchName,
    syncWithGit,
  });
  // A failed health check polls only every 60 s, so its last syncing count is too old to drive the others.
  const isSyncing = !isHealthError && isAnyRepositorySyncing(health);
  const { page: currentPage, query } = useGetBranchRepositories({
    branchName,
    syncWithGit,
    isSyncing,
    page,
    pageSize,
  });

  return (
    <Card className="overflow-hidden" data-testid="branch-repositories-card">
      <CardHeader className="flex items-center gap-2">
        <h2>Git repositories</h2>
        {query.data && (
          <Badge variant="blue" className="rounded-full font-normal tabular-nums">
            {query.data.count}
          </Badge>
        )}
      </CardHeader>

      <BranchRepositoriesBody
        data={query.data}
        error={query.error}
        isPending={query.isPending}
        syncWithGit={syncWithGit}
        branchName={branchName}
        page={currentPage}
        onPageChange={setPage}
      />

      {query.data &&
        query.data.count > 0 &&
        (!health && isHealthError ? (
          <BranchRepositoryHealthFailed />
        ) : (
          <RepositoryErrorBands
            key={branchName}
            repositories={getFailingRepositories(health)}
            unlistedCount={countUnlistedFailures(health)}
            branchName={branchName}
            isSyncing={isSyncing}
          />
        ))}
    </Card>
  );
}

interface BranchRepositoriesBodyProps {
  data: BranchRepositoryPage | undefined;
  error: Error | null;
  isPending: boolean;
  syncWithGit: boolean;
  branchName: string;
  page: number;
  onPageChange: (page: number) => void;
}

function BranchRepositoriesBody({
  data,
  error,
  isPending,
  syncWithGit,
  branchName,
  page,
  onPageChange,
}: BranchRepositoriesBodyProps) {
  if (error && !data) {
    return error instanceof BranchRepositoriesError && error.code === "PERMISSION_DENIED" ? (
      <BranchRepositoriesDenied />
    ) : (
      // A failed page past the first has no pager to leave it, as the count came with the page.
      <BranchRepositoriesFailed onGoToFirstPage={page > 1 ? () => onPageChange(1) : undefined} />
    );
  }
  if (isPending || !data) return <BranchRepositoriesLoading />;
  if (data.count === 0) {
    return syncWithGit ? <BranchRepositoriesNone /> : <BranchRepositoriesNotSynced />;
  }

  // A short last page would otherwise shrink the card and move everything below it.
  const hasMultiplePages = data.count > PAGE_SIZE;

  return (
    <>
      <div
        className="overflow-x-auto"
        data-testid="branch-repositories-table"
        style={hasMultiplePages ? { minHeight: (PAGE_SIZE + 1) * CELL_HEIGHT_PX } : undefined}
      >
        <BranchRepositoriesTable repositories={data.repositories} branchName={branchName} />
      </div>

      {hasMultiplePages && (
        <TablePagination
          className="border-t"
          aria-label="Repositories pagination"
          page={page}
          pageSize={PAGE_SIZE}
          totalCount={data.count}
          onPageChange={onPageChange}
        />
      )}
    </>
  );
}
