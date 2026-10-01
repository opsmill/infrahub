import { Tooltip } from "@infrahub/ui";

import { Row } from "@/shared/components/container";
import { TableCell } from "@/shared/components/table/table-cell";

import type { BranchRepositorySummary } from "@/entities/branches/domain/model/branch-repository-summary";
import { formatSyncStatusCounts } from "@/entities/branches/domain/rules/format-repository-summary";
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
  const worstCount =
    summary.counts.find(({ value }) => value === (worst.syncStatus.value ?? null))?.count ?? 0;
  const countsText = formatSyncStatusCounts(summary.counts);

  return (
    <TableCell className="h-auto min-h-14">
      <Row className="items-center gap-1.5">
        <GitStatePill syncStatus={worst.syncStatus} />

        {total > 1 && (
          <>
            {/* The pill has its own tooltip and react-aria shows one at a time, so only the count carries this one. */}
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
