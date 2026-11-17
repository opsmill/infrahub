import { Tooltip } from "@infrahub/ui";

import { Row } from "@/shared/components/container";
import { TableCell } from "@/shared/components/table/table-cell";

import { formatSyncStatusCounts } from "@/entities/branch-git-status/domain/rules/format-branch-git-status";
import type { BranchTableRow } from "@/entities/branches/ui/branches-table/branch-table-row";
import { GitStatePill } from "@/entities/repository/ui/branch-repositories/git-state-pill";

interface BranchGitStateCellProps {
  branch: BranchTableRow;
}

export function BranchGitStateCell({ branch }: BranchGitStateCellProps) {
  const { gitStatus } = branch;
  const testId = `branch-git-state-cell-${branch.name}`;

  if (gitStatus.status !== "ok") {
    return <TableCell className="h-auto min-h-14" data-testid={testId} />;
  }

  const [worstRepository] = gitStatus.repositories;
  const [worstStatusCount] = gitStatus.counts;

  if (!worstRepository) {
    return <TableCell className="h-auto min-h-14" data-testid={testId} />;
  }

  const total = gitStatus.repositories.length;
  const syncStatusCountsText = formatSyncStatusCounts(gitStatus.counts);

  return (
    <TableCell className="h-auto min-h-14" data-testid={testId}>
      <Row className="items-center gap-1.5">
        <GitStatePill syncStatus={worstRepository.syncStatus} />

        {total > 1 && (
          <>
            {/* Only one tooltip shows at a time and the state already has its own, so the counts go on the n/N text. */}
            <Tooltip message={syncStatusCountsText} nonInteractiveTrigger>
              <span className="text-foreground-muted text-xs">
                {worstStatusCount?.count}/{total}
              </span>
            </Tooltip>
            <span className="sr-only">{syncStatusCountsText}</span>
          </>
        )}
      </Row>
    </TableCell>
  );
}
