import { LinkButton, Spinner, Tooltip } from "@infrahub/ui";
import { useQuery } from "@tanstack/react-query";

import { Icon } from "@/shared/components/display/icon";
import { Pulse } from "@/shared/components/ui/pulse";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getRepositorySyncHealthQueryOptions } from "@/entities/repository/ui/queries/get-repository-sync-health.query";
import { getRepositoriesUrl } from "@/entities/repository/ui/routing/repository-urls";

const REFETCH_INTERVAL = 10_000;

type IndicatorState = "pending" | "check-failed" | "none" | "failing" | "in-sync";

const LABELS: Record<IndicatorState, string> = {
  pending: "Checking Git repository sync status",
  "check-failed": "Git repository sync status could not be checked",
  none: "No Git repositories",
  failing: "Repositories failed to import on this branch",
  "in-sync": "All Git repositories are in sync on this branch",
};

export function RepositorySyncStatus() {
  const { currentBranch } = useCurrentBranch();

  const {
    data: health,
    isPending,
    error,
  } = useQuery({
    ...getRepositorySyncHealthQueryOptions(currentBranch.name),
    refetchInterval: REFETCH_INTERVAL,
  });

  // A failed refresh drops the verdict it can no longer vouch for: a red alarm that keeps
  // pulsing on a reading nobody can refresh is worse than admitting the check did not run.
  const state: IndicatorState = isPending ? "pending" : error || !health ? "check-failed" : health;

  const failing = state === "failing";
  const label = LABELS[state];

  const glyph =
    state === "pending" ? (
      <Spinner />
    ) : state === "check-failed" ? (
      <Icon icon="mdi:error-outline" className="size-4 text-foreground-muted" />
    ) : (
      <Icon icon="mdi:source-branch" className={failing ? "size-4 text-danger" : "size-4"} />
    );

  return (
    <Tooltip message={label}>
      <LinkButton
        shape="square"
        variant="outline"
        size="sm"
        href={getRepositoriesUrl(currentBranch, { onlyFailing: failing })}
        aria-label={label}
        data-testid="repository-sync-status"
        className={state === "none" ? "opacity-60" : undefined}
      >
        <span
          className="flex size-4 items-center justify-center"
          data-testid="repository-sync-status-glyph"
        >
          {glyph}
        </span>
        {failing && (
          <Pulse
            tone="danger"
            // biome-ignore lint/nursery/noTailwindArbitraryValue: pixel-nudge: centres the pulse dot on the button corner; 6.5px is off the 0.25rem grid and has no design meaning
            className="right-[6.5px] bottom-[6.5px]"
            data-testid="repository-sync-status-pulse"
          />
        )}
      </LinkButton>
    </Tooltip>
  );
}
