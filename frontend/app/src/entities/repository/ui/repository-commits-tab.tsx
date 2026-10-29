import { Spinner, Tooltip } from "@infrahub/ui";
import { ArrowDownToLineIcon, GitBranchIcon, TriangleAlertIcon } from "lucide-react";
import { Focusable } from "react-aria-components";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";
import { Pulse } from "@/shared/components/ui/pulse";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { REPOSITORY_COMMITS_TAB } from "@/entities/repository/domain/model/repository";
import { isReadOnlyRepositoryKind } from "@/entities/repository/domain/rules/is-read-only-repository";
import { useIsRebaseOnly } from "@/entities/repository/ui/hooks/use-is-rebase-only";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";
import {
  type CommitsTabBadge,
  formatCommitsTabCount,
  getCommitsTabBadge,
  isLoadingFirstPage,
} from "@/entities/repository/ui/repository-commits.view";

const BADGE_ICONS = {
  "pending-import": ArrowDownToLineIcon,
  behind: GitBranchIcon,
  warning: TriangleAlertIcon,
} as const;

export interface RepositoryCommitsTabProps {
  objectKind: string;
  objectId: string;
  internalStatus: string | null;
}

export function RepositoryCommitsTab({
  objectKind,
  objectId,
  internalStatus,
}: RepositoryCommitsTabProps) {
  const rebaseOnly = useIsRebaseOnly({ repositoryKind: objectKind, internalStatus });
  const isReadOnly = isReadOnlyRepositoryKind(objectKind);
  const {
    isPending,
    failureReason,
    data: badge,
  } = useGetRepositoryCommits(
    { repositoryId: objectId },
    {
      select: ({ pages: [firstPage] }) =>
        firstPage ? getCommitsTabBadge(firstPage, { rebaseOnly, isReadOnly }) : null,
    }
  );
  const to = getObjectDetailsUrl(objectKind, objectId, undefined, REPOSITORY_COMMITS_TAB);

  return (
    <Tooltip message={badge?.tooltip} isDisabled={!badge}>
      <Focusable>
        <LinkTab
          to={to}
          scrollIntoViewOnActive
          aria-label={badge ? `Commits, ${badge.summary}` : undefined}
        >
          Commits
          {isLoadingFirstPage({ isPending, failureReason }) ? (
            <Spinner />
          ) : (
            badge && <CommitsTabBadgeContent badge={badge} />
          )}
        </LinkTab>
      </Focusable>
    </Tooltip>
  );
}

function CommitsTabBadgeContent({ badge }: { badge: CommitsTabBadge }) {
  const Icon = BADGE_ICONS[badge.kind];

  return (
    <Badge
      variant="warning"
      aria-hidden="true"
      className="relative h-5 gap-1 rounded-full py-0 font-medium tabular-nums"
    >
      <Icon className="size-3 shrink-0" strokeWidth={2.25} />
      {badge.kind !== "warning" && formatCommitsTabCount(badge.count)}
      <Pulse tone="warning" className="-top-0.5 -right-0.5" />
    </Badge>
  );
}
