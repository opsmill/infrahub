import { AlertTriangleIcon } from "lucide-react";

import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import { isRepositoryUnreachable } from "@/entities/repository/domain/rules/rank-repositories";
import { GitStatePill } from "@/entities/repository/ui/branch-repositories/git-state-pill";
import { RepositoryNameLink } from "@/entities/repository/ui/branch-repositories/repository-name-link";

interface RepositoryRowProps {
  repository: BranchRepository;
  branchName: string;
  isDefaultBranch: boolean;
}

export function RepositoryRow({ repository, branchName, isDefaultBranch }: RepositoryRowProps) {
  const { commit, syncStatus, operationalStatus } = repository;
  const unreachableLabel = isRepositoryUnreachable(repository)
    ? operationalStatus.label || operationalStatus.value
    : null;

  return (
    <tr className="h-10 border-b last:border-b-0">
      <td className="px-3">
        <RepositoryNameLink
          repository={repository}
          branchName={branchName}
          isDefaultBranch={isDefaultBranch}
        />
      </td>
      <td className="px-3">
        <span className="flex items-center gap-1.5">
          <GitStatePill syncStatus={syncStatus} />
          {unreachableLabel && (
            <AlertTriangleIcon
              role="img"
              className="size-3.5 shrink-0 text-warning"
              aria-label={unreachableLabel}
            />
          )}
        </span>
      </td>
      <td className="px-3 font-mono text-xs tabular-nums">
        {commit ? (
          <span className="block truncate" title={commit}>
            {commit}
          </span>
        ) : (
          <span className="text-foreground-muted">—</span>
        )}
      </td>
    </tr>
  );
}
