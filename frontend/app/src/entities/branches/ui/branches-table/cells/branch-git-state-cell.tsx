import { Tooltip } from "@infrahub/ui";

import { Row } from "@/shared/components/container";
import { TableCell } from "@/shared/components/table/table-cell";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import { rankRepositories } from "@/entities/repository/domain/rules/rank-repositories";
import { GitStatePill } from "@/entities/repository/ui/branch-repositories/git-state-pill";
import { useGetBranchRepositories } from "@/entities/repository/ui/queries/get-branch-repositories.query";

interface BranchGitStateCellProps {
  branch: BranchListItem;
}

export function BranchGitStateCell({ branch }: BranchGitStateCellProps) {
  const { data, isError } = useGetBranchRepositories({
    branchName: branch.name,
    syncWithGit: Boolean(branch.sync_with_git),
  });

  const ranked = !isError && data?.status === "ok" ? rankRepositories(data.repositories) : [];
  const [worst] = ranked;

  if (!worst) {
    return <TableCell className="h-auto min-h-14" />;
  }

  const counts = countBySyncStatus(ranked);
  const worstCount = counts.get(worst.syncStatus.value)?.count ?? 0;

  return (
    <TableCell className="h-auto min-h-14">
      <Row className="items-center gap-1.5">
        <GitStatePill syncStatus={worst.syncStatus} />

        {ranked.length > 1 && (
          // The pill has its own tooltip and react-aria shows one at a time, so only the count carries this one.
          <Tooltip
            message={[...counts.values()]
              .map(({ label, count }) => `${label}: ${count}`)
              .join(" · ")}
            nonInteractiveTrigger
          >
            <span className="text-foreground-muted text-xs">
              {worstCount}/{ranked.length}
            </span>
          </Tooltip>
        )}
      </Row>
    </TableCell>
  );
}

function countBySyncStatus(repositories: BranchRepository[]) {
  const counts = new Map<string | null, { label: string; count: number }>();
  for (const { syncStatus } of repositories) {
    const entry = counts.get(syncStatus.value);
    if (entry) {
      entry.count += 1;
    } else {
      counts.set(syncStatus.value, {
        label: syncStatus.label || syncStatus.value || "Unknown",
        count: 1,
      });
    }
  }
  return counts;
}
