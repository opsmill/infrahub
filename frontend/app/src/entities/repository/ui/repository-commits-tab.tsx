import { Spinner, Tooltip } from "@infrahub/ui";
import { ArrowDownToLineIcon, GitBranchIcon, TriangleAlertIcon } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_COMMITS_TAB,
} from "@/entities/repository/domain/model/repository";
import { isRebaseOnly } from "@/entities/repository/domain/rules/is-rebase-only";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";
import {
  type CommitsTabBadge,
  formatCommitsTabCount,
  getCommitsTabBadge,
  isLoadingFirstPage,
} from "@/entities/repository/ui/repository-commits.view";

const TOOLTIP_DELAY_MS = 200;

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
  const { currentBranch } = useCurrentBranch();
  const rebaseOnly = isRebaseOnly({
    repositoryKind: objectKind,
    internalStatus,
    isDefaultBranch: currentBranch.is_default,
    syncWithGit: currentBranch.sync_with_git,
  });
  const isReadOnly = objectKind === READONLY_REPOSITORY_KIND;
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

  if (isLoadingFirstPage({ isPending, failureReason })) {
    return (
      <LinkTab to={to}>
        Commits
        <Spinner />
      </LinkTab>
    );
  }

  if (!badge) {
    return <LinkTab to={to}>Commits</LinkTab>;
  }

  return (
    <LinkTabWithTooltip to={to} tooltip={badge.tooltip} ariaLabel={`Commits, ${badge.summary}`}>
      Commits
      <CommitsTabBadgeContent badge={badge} />
    </LinkTabWithTooltip>
  );
}

function CommitsTabBadgeContent({ badge }: { badge: CommitsTabBadge }) {
  const Icon = BADGE_ICONS[badge.kind];

  return (
    <Badge
      variant="warning"
      aria-hidden="true"
      className="h-5 gap-1 rounded-full py-0 font-medium tabular-nums"
    >
      <Icon className="size-3 shrink-0" strokeWidth={2.25} />
      {badge.kind !== "warning" && formatCommitsTabCount(badge.count)}
    </Badge>
  );
}

interface LinkTabWithTooltipProps {
  to: string;
  tooltip: string;
  ariaLabel: string;
  children: ReactNode;
}

// Opened by the link's own handlers: a non-interactive tooltip trigger inside a link never receives keyboard focus.
function LinkTabWithTooltip({ to, tooltip, ariaLabel, children }: LinkTabWithTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const openTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => () => clearTimeout(openTimer.current), []);

  const open = (delay: number) => {
    clearTimeout(openTimer.current);
    openTimer.current = setTimeout(() => setIsOpen(true), delay);
  };
  const close = () => {
    clearTimeout(openTimer.current);
    setIsOpen(false);
  };

  return (
    <LinkTab
      to={to}
      aria-label={ariaLabel}
      onMouseEnter={() => open(TOOLTIP_DELAY_MS)}
      onMouseLeave={close}
      onClick={close}
      onFocus={(event) => {
        if (event.currentTarget.matches(":focus-visible")) open(0);
      }}
      onBlur={close}
      onKeyDown={(event) => {
        if (event.key === "Escape") close();
      }}
    >
      <Tooltip message={tooltip} isOpen={isOpen} onOpenChange={setIsOpen} triggerRef={triggerRef}>
        <span ref={triggerRef} className="inline-flex items-center gap-2">
          {children}
        </span>
      </Tooltip>
    </LinkTab>
  );
}
