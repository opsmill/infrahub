import { Tooltip } from "@infrahub/ui";
import { AlertTriangleIcon, FolderGitIcon } from "lucide-react";

import { Row } from "@/shared/components/container";
import { Link } from "@/shared/components/ui/link";

import { getBranchQsp } from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import { isRepositoryUnreachable } from "@/entities/repository/domain/rules/repository-failures";
import { GitStatePill } from "@/entities/repository/ui/branch-repositories/git-state-pill";

interface RepositoryRowProps {
  repository: BranchRepository;
  branchName: string;
}

export function RepositoryRow({ repository, branchName }: RepositoryRowProps) {
  const { id, kind, name, isReadOnly, commit, syncStatus, operationalStatus } = repository;
  const unreachableLabel = isRepositoryUnreachable(repository)
    ? operationalStatus.label || operationalStatus.value
    : null;

  return (
    <tr className="h-10 border-b last:border-b-0">
      <td className="px-3">
        <Row className="min-w-0 gap-1.5">
          <FolderGitIcon className="size-3.5 shrink-0 text-foreground-muted" aria-hidden />
          <Link
            to={getObjectDetailsUrl(kind, id, [getBranchQsp(branchName)])}
            title={name}
            className="truncate"
          >
            {name}
          </Link>
          {isReadOnly && (
            <span className="shrink-0 rounded bg-content-strong px-1 text-foreground-muted text-xs">
              Read-only
            </span>
          )}
        </Row>
      </td>
      <td className="px-3">
        <Row className="gap-1.5">
          <GitStatePill syncStatus={syncStatus} />
          {unreachableLabel && (
            <Tooltip message={unreachableLabel} nonInteractiveTrigger>
              <span className="inline-flex">
                <AlertTriangleIcon
                  role="img"
                  className="size-3.5 shrink-0 text-warning"
                  aria-label={unreachableLabel}
                />
              </span>
            </Tooltip>
          )}
        </Row>
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
