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
 * Each state names the condition rather than the control, so the text stands on its own when
 * read by assistive technology. Repositories are not per-branch, so the empty case does not
 * describe itself as a property of the current branch.
 */
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
    // Muted, never the danger colour: a viewer who cannot read repositories fails this
    // lookup on every page, and an alarm they can never clear would drown out a real one.
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

  // Both lookups ask about the present, deliberately ignoring any time-frame selection: a
  // historical "all clear" shown on a branch that is broken right now is the failure this
  // indicator exists to prevent. The shared count hook inherits that selection, so the query
  // options are composed here instead.
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
      {/* Fixed slot, so the header cannot shift as the glyph inside it changes. */}
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

  // With no repositories there is nowhere to navigate to, so the control is a button rather
  // than a link. It stays hoverable while looking disabled, because a control that cannot be
  // hovered cannot show the tooltip that explains why it is inactive.
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
