import { getBranchQsp } from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import { RepositoryErrorBand } from "@/entities/repository/ui/branch-repositories/repository-error-band";

interface UnreachableBandProps {
  repository: BranchRepository;
  branchName: string;
}

export function UnreachableBand({ repository, branchName }: UnreachableBandProps) {
  const { id, kind, name, operationalStatus } = repository;

  return (
    <RepositoryErrorBand
      tone="warning"
      repositoryName={name}
      problem={operationalStatus.label || operationalStatus.value}
      action={{
        to: getObjectDetailsUrl(kind, id, [getBranchQsp(branchName)]),
        label: "Open repository",
      }}
    >
      <p className="text-warning-strong text-xs leading-relaxed">
        Infrahub can't fetch new commits, so the commit shown may be out of date. Check the
        repository's credentials and location.
      </p>
    </RepositoryErrorBand>
  );
}
