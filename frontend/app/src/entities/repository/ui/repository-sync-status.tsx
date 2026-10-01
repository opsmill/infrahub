import { LinkButton, Spinner, Tooltip } from "@infrahub/ui";
import { useQuery } from "@tanstack/react-query";

import { Icon } from "@/shared/components/display/icon";
import { Pulse } from "@/shared/components/ui/pulse";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getRepositorySyncHealthQueryOptions } from "@/entities/repository/ui/queries/get-repository-sync-health.query";
import { getRepositoriesUrl } from "@/entities/repository/ui/routing/repository-urls";

const REFETCH_INTERVAL = 10_000;

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

  const failing = health === "failing";
  const tooltip = isPending
    ? "Checking Git repository sync status"
    : error
      ? "Git repository sync status could not be checked"
      : failing
        ? "Repositories failed to import on this branch"
        : health === "none"
          ? "No Git repositories"
          : "All Git repositories are in sync on this branch";

  const glyph = isPending ? (
    <Spinner />
  ) : error ? (
    <Icon icon="mdi:error-outline" className="size-4 text-foreground-muted" />
  ) : (
    <Icon icon="mdi:source-branch" className={failing ? "size-4 text-danger" : "size-4"} />
  );

  return (
    <Tooltip message={tooltip}>
      <LinkButton
        shape="square"
        variant="outline"
        size="sm"
        href={getRepositoriesUrl(currentBranch, { onlyFailing: failing })}
        aria-label={tooltip}
        data-testid="repository-sync-status"
        className={health === "none" ? "opacity-60" : undefined}
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
