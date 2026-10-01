import { Badge, type BadgeProps } from "@/shared/components/ui/badge";

import {
  type RepositoryCommit,
  RepositoryCommitState,
} from "@/entities/repository/domain/model/repository";

interface StateBadge {
  label: string;
  variant: BadgeProps["variant"];
}

const REMOTE_HEAD_BADGE: StateBadge = { label: "Remote head", variant: "blue" };
const IMPORTED_BADGE: StateBadge = { label: "Imported", variant: "green" };
const PENDING_BADGE: StateBadge = { label: "Pending import", variant: "yellow" };
const UNRELATED_BADGE: StateBadge = { label: "Not on current history", variant: "gray-outline" };

function getStateBadges(commit: RepositoryCommit, importedCommit: string | null): StateBadge[] {
  switch (commit.state) {
    case RepositoryCommitState.HEAD:
      return commit.hash === importedCommit
        ? [REMOTE_HEAD_BADGE, IMPORTED_BADGE]
        : [REMOTE_HEAD_BADGE];
    case RepositoryCommitState.IMPORTED:
      return [IMPORTED_BADGE];
    case RepositoryCommitState.PENDING:
      return [PENDING_BADGE];
    case RepositoryCommitState.UNRELATED:
      return [UNRELATED_BADGE];
    case RepositoryCommitState.HISTORY:
      return [];
  }
}

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
