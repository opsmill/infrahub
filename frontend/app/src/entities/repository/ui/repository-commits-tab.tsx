import { Spinner, Tooltip } from "@infrahub/ui";
import { ArrowDownToLineIcon, GitBranchIcon, TriangleAlertIcon } from "lucide-react";
import { type ReactNode, useRef, useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_COMMITS_TAB,
} from "@/entities/repository/domain/model/repository";
import { isUpdatedOnlyByRebase } from "@/entities/repository/domain/rules/is-updated-only-by-rebase";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";
import {
  type CommitsTabSignal,
  formatCommitsTabCount,
  getCommitsTabSignal,
  isLoadingFirstPage,
} from "@/entities/repository/ui/repository-commits.view";

const TOOLTIP_DELAY_MS = 200;

const SIGNAL_ICONS = {
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
  const updatedOnlyByRebase = isUpdatedOnlyByRebase({
    repositoryKind: objectKind,
    internalStatus,
    branch: currentBranch,
  });
  const isReadOnly = objectKind === READONLY_REPOSITORY_KIND;
  const {
    isPending,
    failureReason,
    data: signal,
  } = useGetRepositoryCommits(
    { repositoryId: objectId },
    {
      select: ({ pages: [firstPage] }) =>
        firstPage ? getCommitsTabSignal(firstPage, { updatedOnlyByRebase, isReadOnly }) : null,
    }
  );
  const to = getObjectDetailsUrl(objectKind, objectId, undefined, REPOSITORY_COMMITS_TAB);

  if (isLoadingFirstPage({ isPending, failureReason })) {
    return (
      <LinkTab to={to} scrollIntoViewOnActive>
        Commits
        <Spinner />
      </LinkTab>
    );
  }

  if (!signal) {
    return (
      <LinkTab to={to} scrollIntoViewOnActive>
        Commits
      </LinkTab>
    );
  }

  return (
    <LinkTabWithTooltip to={to} tooltip={signal.hint} label={`Commits, ${signal.description}`}>
      Commits
      <CommitsTabPill signal={signal} />
    </LinkTabWithTooltip>
  );
}

function CommitsTabPill({ signal }: { signal: CommitsTabSignal }) {
  const Icon = SIGNAL_ICONS[signal.kind];

  return (
    <Badge
      variant="warning"
      aria-hidden="true"
      className="h-5 gap-1 rounded-full py-0 font-medium tabular-nums"
    >
      <Icon className="size-3 shrink-0" strokeWidth={2.25} />
      {signal.kind !== "warning" && formatCommitsTabCount(signal.count)}
    </Badge>
  );
}

interface LinkTabWithTooltipProps {
  to: string;
  tooltip: string;
  label: string;
  children: ReactNode;
}

// Opened by the link's own handlers: a non-interactive tooltip trigger inside a link never receives keyboard focus.
function LinkTabWithTooltip({ to, tooltip, label, children }: LinkTabWithTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const openTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

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
      scrollIntoViewOnActive
      aria-label={label}
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
