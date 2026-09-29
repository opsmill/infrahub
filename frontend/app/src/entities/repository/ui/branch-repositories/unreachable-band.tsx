import { AlertTriangleIcon } from "lucide-react";

import { Link } from "@/shared/components/ui/link";

import { getBranchQspOverride } from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";

interface UnreachableBandProps {
  repository: BranchRepository;
  branchName: string;
  isDefaultBranch: boolean;
}

export function UnreachableBand({ repository, branchName, isDefaultBranch }: UnreachableBandProps) {
  const { id, kind, name, operationalStatus } = repository;

  return (
    <div
      className="flex items-start gap-2.5 border-warning-border border-t bg-warning-surface px-4 py-3"
      data-testid="repository-error-band"
    >
      <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="font-semibold text-sm text-warning-strong">
          <span className="break-all">{name}</span> —{" "}
          {operationalStatus.label || operationalStatus.value}
        </div>
        <p className="text-warning-strong text-xs leading-relaxed">
          Infrahub can't fetch new commits, so the commit shown may be out of date. Check the
          repository's credentials and location.
        </p>
      </div>
      <Link
        to={getObjectDetailsUrl(kind, id, [getBranchQspOverride(branchName, isDefaultBranch)])}
        className="shrink-0 px-2 py-1 font-medium text-warning-strong text-xs"
      >
        Open repository
      </Link>
    </div>
  );
}
