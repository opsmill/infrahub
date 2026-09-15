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

/** Matches the task indicator's cadence so the two header controls behave alike. */
const REFETCH_INTERVAL = 10_000;

/**
 * Each state names the condition, not the control, so the text is useful on its own to anyone
 * reading it through assistive technology.
 */
const TOOLTIP_BY_STATUS: Record<GitStatusValue, string> = {
  // The inert label deliberately avoids the word "branch": repositories are branch-agnostic,
  // so "none on this branch" would be inaccurate, and it also collided with an e2e locator
  // matching buttons by the accessible-name substring "Branch".
  loading: "Checking Git status",
  "check-failed": "Git status could not be checked",
  inert: "No Git repositories configured",
  error: "Repositories failed to import on this branch",
  neutral: "All Git repositories are in sync on this branch",
};

function GitStatusGlyph({ status }: { status: GitStatusValue }) {
  if (status === "loading") return <Spinner />;

  if (status === "check-failed") {
    // Muted, never the danger colour: an operator who cannot read repositories fails this
    // lookup on every page, and a red alarm they can never clear would drown out a real one.
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

  // `getObjectsCountQueryOptions` is used directly rather than the `useObjectsCount` hook,
  // which inherits the header time-machine's date from `datetimeAtom`. This indicator must
  // always report health as of now: showing a historical "all clear" on a branch that is
  // broken right now is the exact failure it exists to prevent.
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
      {/* Fixed slot: the spinner and the two icons must not resize the header between
          states, so the box is pinned rather than left to whatever each glyph measures. */}
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

  // With no repositories there is nowhere useful to send the operator, so the control becomes
  // a button rather than a link. `isDisabledAndFocusable` is what keeps it hoverable while
  // looking disabled — a `LinkButton` with `isDisabled` picks up `pointer-events-none`, which
  // swallows the hover and leaves the state with no explanation at all (FR-010a).
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
