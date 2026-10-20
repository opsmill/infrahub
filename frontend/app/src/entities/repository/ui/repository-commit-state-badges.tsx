import { Badge } from "@/shared/components/ui/badge";

import type { RepositoryCommit } from "@/entities/repository/domain/model/repository";
import {
  type CommitStateContext,
  getStateBadges,
} from "@/entities/repository/ui/repository-commits.view";

export interface RepositoryCommitStateBadgesProps extends CommitStateContext {
  commit: RepositoryCommit;
}

export function RepositoryCommitStateBadges({
  commit,
  ...context
}: RepositoryCommitStateBadgesProps) {
  return getStateBadges(commit, context).map(({ label, variant }) => (
    <Badge key={label} variant={variant}>
      {label}
    </Badge>
  ));
}
