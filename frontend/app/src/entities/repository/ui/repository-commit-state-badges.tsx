import { Badge } from "@/shared/components/ui/badge";

import type { RepositoryCommit } from "@/entities/repository/domain/model/repository";
import { getStateBadges } from "@/entities/repository/ui/repository-commits.view";

export interface RepositoryCommitStateBadgesProps {
  commit: RepositoryCommit;
  importedCommit: string | null;
}

export function RepositoryCommitStateBadges({
  commit,
  importedCommit,
}: RepositoryCommitStateBadgesProps) {
  return getStateBadges(commit, importedCommit).map(({ label, variant }) => (
    <Badge key={label} variant={variant}>
      {label}
    </Badge>
  ));
}
