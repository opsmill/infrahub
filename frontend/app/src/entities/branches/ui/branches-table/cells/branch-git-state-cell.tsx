import { Tooltip } from "@infrahub/ui";

import { Row } from "@/shared/components/container";
import { TableCell } from "@/shared/components/table/table-cell";

import type { BranchRepositorySummary } from "@/entities/branches/domain/model/branch-repository-summary";
import {
  countRepositoriesInState,
  formatSyncStatusCounts,
} from "@/entities/branches/domain/rules/format-repository-summary";
import { GitStatePill } from "@/entities/repository/ui/branch-repositories/git-state-pill";

interface BranchGitStateCellProps {
  summary: BranchRepositorySummary;
}

export function BranchGitStateCell({ summary }: BranchGitStateCellProps) {
  const [worst] = summary.status === "ok" ? summary.repositories : [];

  if (summary.status !== "ok" || !worst) {
    return <TableCell className="h-auto min-h-14" />;
  }

  const total = summary.repositories.length;
  const worstCount = countRepositoriesInState(summary.counts, worst);
  const countsText = formatSyncStatusCounts(summary.counts);

  return (
    <TableCell className="h-auto min-h-14">
      <Row className="items-center gap-1.5">
        <GitStatePill syncStatus={worst.syncStatus} />

        {total > 1 && (
          <>
            {/* Only one tooltip shows at a time and the state already has its own, so the counts go on the n/N text. */}
            <Tooltip message={countsText} nonInteractiveTrigger>
              <span className="text-foreground-muted text-xs">
                {worstCount}/{total}
              </span>
            </Tooltip>
            <span className="sr-only">{countsText}</span>
          </>
        )}
      </Row>
    </TableCell>
  );
}
