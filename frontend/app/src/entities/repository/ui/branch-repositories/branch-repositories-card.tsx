import { PagedTableCard } from "@/shared/components/table/paged-table-card";
import { useTablePagination } from "@/shared/hooks/use-table-pagination";

import { isRepositoryAccessDenied } from "@/entities/repository/domain/rules/branch-repositories-error";
import {
  countUnlistedFailures,
  getFailingRepositories,
} from "@/entities/repository/domain/rules/repository-failures";
import { isAnyRepositorySyncing } from "@/entities/repository/domain/rules/repository-syncing";
import { BranchRepositoriesTable } from "@/entities/repository/ui/branch-repositories/branch-repositories-table";
import {
  RepositoryErrorBands,
  RepositoryHealthFailedBand,
} from "@/entities/repository/ui/branch-repositories/repository-error-bands";
import { useGetBranchRepositories } from "@/entities/repository/ui/queries/get-branch-repositories.query";
import { useGetBranchRepositoryHealth } from "@/entities/repository/ui/queries/get-branch-repository-health.query";

const REPOSITORIES_URL_KEY = "repositories";

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
  // A failed health refetch keeps its last data, which can no longer say whether a sync is running.
  const isSyncing = !isHealthError && isAnyRepositorySyncing(health);
  const query = useGetBranchRepositories({
    branchName,
    syncWithGit,
    isSyncing,
    page,
    pageSize,
  });

  return (
    <PagedTableCard
      title="Git repositories"
      itemName={{ one: "repository", other: "repositories" }}
      query={query}
      page={page}
      pageSize={pageSize}
      onPageChange={setPage}
      isDenied={isRepositoryAccessDenied}
      deniedMessage="You don't have access to this branch's repositories. Ask an administrator for permission to view repositories."
      failedMessage="Repositories couldn't be loaded."
      emptyTitle={syncWithGit ? "No Git repositories" : "Not synchronised with Git"}
      emptyMessage={
        syncWithGit
          ? "Repositories connected to Infrahub will show here with their Git state on this branch."
          : "This branch was created with Sync with Git off, so repository imports and generators don't run on it."
      }
      renderTable={(data) => (
        <BranchRepositoriesTable repositories={data.repositories} branchName={branchName} />
      )}
      tableTestId="branch-repositories-table"
      footer={
        !health && isHealthError ? (
          <RepositoryHealthFailedBand />
        ) : (
          <RepositoryErrorBands
            key={branchName}
            repositories={getFailingRepositories(health)}
            unlistedCount={countUnlistedFailures(health)}
            branchName={branchName}
            isSyncing={isSyncing}
          />
        )
      }
      data-testid="branch-repositories-card"
    />
  );
}
