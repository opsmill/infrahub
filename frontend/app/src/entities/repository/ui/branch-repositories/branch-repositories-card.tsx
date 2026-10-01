import { Card, CardHeader } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { Link } from "@/shared/components/ui/link";

import { getBranchQspOverride } from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { BranchRepositoriesResult } from "@/entities/repository/domain/model/branch-repository";
import { isRepositorySyncing } from "@/entities/repository/domain/rules/is-repository-syncing";
import { getRepositoryListKind } from "@/entities/repository/domain/use-cases/get-branch-repositories";
import {
  BranchRepositoriesDenied,
  BranchRepositoriesFailed,
  BranchRepositoriesLoading,
  BranchRepositoriesNone,
  BranchRepositoriesNotSynced,
} from "@/entities/repository/ui/branch-repositories/branch-repositories-states";
import { BranchRepositoriesTable } from "@/entities/repository/ui/branch-repositories/branch-repositories-table";
import { RepositoryErrorBands } from "@/entities/repository/ui/branch-repositories/repository-error-bands";
import { useGetBranchRepositories } from "@/entities/repository/ui/queries/get-branch-repositories.query";

interface BranchRepositoriesCardProps {
  branchName: string;
  isDefaultBranch: boolean;
  syncWithGit: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

export function BranchRepositoriesCard({
  branchName,
  isDefaultBranch,
  syncWithGit,
  page,
  onPageChange,
}: BranchRepositoriesCardProps) {
  const { data, error, isPending } = useGetBranchRepositories({ branchName, syncWithGit });
  const count = data?.status === "ok" ? data.count : null;

  return (
    <Card className="overflow-hidden" data-testid="branch-repositories-card">
      <CardHeader className="flex items-center gap-2">
        <h2>Git repositories</h2>
        {count !== null && (
          <Badge variant="blue" className="rounded-full font-normal tabular-nums">
            {count}
          </Badge>
        )}
      </CardHeader>

      <BranchRepositoriesBody
        data={data}
        errorMessage={error?.message}
        isPending={isPending}
        branchName={branchName}
        isDefaultBranch={isDefaultBranch}
        syncWithGit={syncWithGit}
        page={page}
        onPageChange={onPageChange}
      />
    </Card>
  );
}

interface BranchRepositoriesBodyProps extends BranchRepositoriesCardProps {
  data: BranchRepositoriesResult | undefined;
  errorMessage: string | undefined;
  isPending: boolean;
}

function BranchRepositoriesBody({
  data,
  errorMessage,
  isPending,
  branchName,
  isDefaultBranch,
  syncWithGit,
  page,
  onPageChange,
}: BranchRepositoriesBodyProps) {
  if (isPending) return <BranchRepositoriesLoading />;
  if (!data) return <BranchRepositoriesFailed errorMessage={errorMessage} />;
  if (data.status === "denied") return <BranchRepositoriesDenied />;
  if (data.repositories.length === 0) {
    return syncWithGit ? <BranchRepositoriesNone /> : <BranchRepositoriesNotSynced />;
  }

  const { repositories, count, isTruncated } = data;

  return (
    <>
      <BranchRepositoriesTable
        repositories={repositories}
        branchName={branchName}
        isDefaultBranch={isDefaultBranch}
        page={page}
        onPageChange={onPageChange}
      />
      <RepositoryErrorBands
        repositories={repositories}
        branchName={branchName}
        isDefaultBranch={isDefaultBranch}
        isSyncing={repositories.some(isRepositorySyncing)}
      />
      {isTruncated && (
        <p className="border-t px-4 py-2 text-foreground-muted text-xs">
          Showing the first {repositories.length} of {count} repositories.{" "}
          <Link
            to={getObjectDetailsUrl(getRepositoryListKind(syncWithGit), undefined, [
              getBranchQspOverride(branchName, isDefaultBranch),
            ])}
          >
            View all repositories
          </Link>
        </p>
      )}
    </>
  );
}
