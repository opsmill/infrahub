import { Button, LinkButton, Spinner, Tooltip } from "@infrahub/ui";
import { useQuery } from "@tanstack/react-query";

import { Icon } from "@/shared/components/display/icon";
import { Pulse } from "@/shared/components/ui/pulse";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectsCountQueryOptions } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_ERROR_IMPORT_FILTER,
} from "@/entities/repository/domain/model/repository";
import {
  deriveGitStatus,
  type GitStatus as GitStatusValue,
} from "@/entities/repository/domain/rules/derive-git-status";
import { getFailingRepositoriesUrl } from "@/entities/repository/ui/routing/repository-urls";

const REFETCH_INTERVAL = 10_000;

const TOOLTIP_BY_STATUS: Record<GitStatusValue, string> = {
  loading: "Checking Git status",
  "check-failed": "Git status could not be checked",
  inert: "No Git repositories configured",
  error: "Repositories failed to import on this branch",
  neutral: "All Git repositories are in sync on this branch",
};

function GitStatusGlyph({ status }: { status: GitStatusValue }) {
  if (status === "loading") return <Spinner />;

  if (status === "check-failed") {
    return <Icon icon="mdi:error-outline" className="size-4 text-foreground-muted" />;
  }

  return (
    <Icon
      icon="mdi:source-branch"
      className={status === "error" ? "size-4 text-danger" : "size-4"}
    />
  );
}

export function GitStatus() {
  const { currentBranch } = useCurrentBranch();

  // `atDate: null` keeps both counts on current state, whatever time frame is selected.
  const countOptions = (filters?: typeof REPOSITORY_ERROR_IMPORT_FILTER) =>
    getObjectsCountQueryOptions({
      objectKind: GENERIC_REPOSITORY_KIND,
      branchName: currentBranch.name,
      atDate: null,
      ...(filters ? { filters: [filters] } : {}),
    });

  const total = useQuery({ ...countOptions(), refetchInterval: REFETCH_INTERVAL });
  const failing = useQuery({
    ...countOptions(REPOSITORY_ERROR_IMPORT_FILTER),
    refetchInterval: REFETCH_INTERVAL,
  });

  const status = deriveGitStatus({
    totalIsPending: total.isPending,
    totalError: total.error,
    totalCount: total.data,
    failingIsPending: failing.isPending,
    failingError: failing.error,
    failingCount: failing.data,
  });

  const tooltipContent = TOOLTIP_BY_STATUS[status];

  const content = (
    <>
      <span className="flex size-4 items-center justify-center" data-testid="git-status-glyph">
        <GitStatusGlyph status={status} />
      </span>
      {status === "error" && (
        <Pulse
          tone="danger"
          className="right-[6.5px] bottom-[6.5px]"
          data-testid="git-status-pulse"
        />
      )}
    </>
  );

  const sharedProps = {
    shape: "square",
    variant: "outline",
    size: "sm",
    "aria-label": tooltipContent,
    "data-testid": "git-status",
  } as const;

  // `isDisabledAndFocusable` keeps the tooltip reachable; `isDisabled` would block hover.
  if (status === "inert") {
    return (
      <Tooltip message={tooltipContent}>
        <Button {...sharedProps} isDisabledAndFocusable>
          {content}
        </Button>
      </Tooltip>
    );
  }

  return (
    <Tooltip message={tooltipContent}>
      <LinkButton {...sharedProps} href={getFailingRepositoriesUrl(currentBranch)}>
        {content}
      </LinkButton>
    </Tooltip>
  );
}
