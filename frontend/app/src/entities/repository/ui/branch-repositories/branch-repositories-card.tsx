import { Card, CardHeader } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";

import type { BranchRepositoriesResult } from "@/entities/repository/domain/model/branch-repository";
import {
  BranchRepositoriesDenied,
  BranchRepositoriesFailed,
  BranchRepositoriesLoading,
  BranchRepositoriesNone,
  BranchRepositoriesNotSynced,
} from "@/entities/repository/ui/branch-repositories/branch-repositories-states";
import { BranchRepositoriesTable } from "@/entities/repository/ui/branch-repositories/branch-repositories-table";
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
  const { data, isPending } = useGetBranchRepositories({ branchName, syncWithGit });
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
  isPending: boolean;
}

function BranchRepositoriesBody({
  data,
  isPending,
  branchName,
  isDefaultBranch,
  syncWithGit,
  page,
  onPageChange,
}: BranchRepositoriesBodyProps) {
  if (isPending) return <BranchRepositoriesLoading />;
  if (!data) return <BranchRepositoriesFailed />;
  if (data.status === "denied") return <BranchRepositoriesDenied />;
  if (data.repositories.length === 0) {
    return syncWithGit ? <BranchRepositoriesNone /> : <BranchRepositoriesNotSynced />;
  }

  return (
    <BranchRepositoriesTable
      repositories={data.repositories}
      count={data.count}
      isTruncated={data.isTruncated}
      branchName={branchName}
      isDefaultBranch={isDefaultBranch}
      page={page}
      onPageChange={onPageChange}
    />
  );
}
