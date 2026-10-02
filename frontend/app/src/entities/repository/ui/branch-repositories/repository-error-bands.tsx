import { Button } from "@infrahub/ui";
import { useState } from "react";

import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import { MAX_VISIBLE_BANDS } from "@/entities/repository/domain/model/repository";
import { getBandKind } from "@/entities/repository/domain/rules/repository-failures";
import { ImportErrorBand } from "@/entities/repository/ui/branch-repositories/import-error-band";
import { UnreachableBand } from "@/entities/repository/ui/branch-repositories/unreachable-band";

interface RepositoryErrorBandsProps {
  repositories: BranchRepository[];
  unlistedCount?: number;
  branchName: string;
  isSyncing: boolean;
}

const pluralizeRepositories = (count: number) => (count === 1 ? "repository" : "repositories");

// Hidden bands aren't mounted, so their import logs are only fetched once Show all opens them.
export function RepositoryErrorBands({
  repositories,
  unlistedCount = 0,
  branchName,
  isSyncing,
}: RepositoryErrorBandsProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  if (repositories.length === 0) return null;

  const visible = isExpanded ? repositories : repositories.slice(0, MAX_VISIBLE_BANDS);
  const hidden = repositories.slice(MAX_VISIBLE_BANDS);
  const andMore = unlistedCount > 0 ? ` and ${unlistedCount} more` : "";
  const hiddenCount = hidden.length + unlistedCount;

  return (
    <>
      {visible.map((repository) =>
        getBandKind(repository) === "import-error" ? (
          <ImportErrorBand
            key={repository.id}
            repository={repository}
            branchName={branchName}
            isSyncing={isSyncing}
          />
        ) : (
          <UnreachableBand key={repository.id} repository={repository} branchName={branchName} />
        )
      )}

      {hidden.length > 0 && (
        <div className="flex items-center justify-between gap-2 border-danger/30 border-t bg-danger-surface px-4 py-2 text-danger-strong text-xs">
          <span className="tabular-nums">
            {isExpanded
              ? `${repositories.length} repositories with errors${andMore}`
              : `${hiddenCount} more ${pluralizeRepositories(hiddenCount)} with errors: ${hidden.map(({ name }) => name).join(", ")}${andMore}`}
          </span>
          <Button variant="ghost" size="xs" onPress={() => setIsExpanded((value) => !value)}>
            {isExpanded ? "Collapse" : "Show all"}
          </Button>
        </div>
      )}
    </>
  );
}
