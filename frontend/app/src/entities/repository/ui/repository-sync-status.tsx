import { LinkButton, Spinner, Tooltip } from "@infrahub/ui";

import { Icon } from "@/shared/components/display/icon";
import { Pulse } from "@/shared/components/ui/pulse";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { RepositorySyncIndicator } from "@/entities/repository/domain/rules/derive-repository-sync-indicator";
import { useRepositorySyncIndicator } from "@/entities/repository/ui/queries/get-repository-sync-indicator.query";
import { getRepositoriesUrl } from "@/entities/repository/ui/routing/repository-urls";

const TOOLTIP: Record<RepositorySyncIndicator, string> = {
  loading: "Checking Git repository sync status",
  "check-failed": "Git repository sync status could not be checked",
  "no-repositories": "No Git repositories configured",
  failing: "Repositories failed to import on this branch",
  "in-sync": "All Git repositories are in sync on this branch",
};

function SyncGlyph({ indicator }: { indicator: RepositorySyncIndicator }) {
  if (indicator === "loading") return <Spinner />;

  if (indicator === "check-failed") {
    return <Icon icon="mdi:error-outline" className="size-4 text-foreground-muted" />;
  }

  return (
    <Icon
      icon="mdi:source-branch"
      className={indicator === "failing" ? "size-4 text-danger" : "size-4"}
    />
  );
}

export function RepositorySyncStatus() {
  const { currentBranch } = useCurrentBranch();
  const indicator = useRepositorySyncIndicator();
  const tooltip = TOOLTIP[indicator];

  return (
    <Tooltip message={tooltip}>
      <LinkButton
        shape="square"
        variant="outline"
        size="sm"
        href={getRepositoriesUrl(currentBranch, { onlyFailing: indicator === "failing" })}
        aria-label={tooltip}
        data-testid="repository-sync-status"
        className={indicator === "no-repositories" ? "opacity-60" : undefined}
      >
        <span
          className="flex size-4 items-center justify-center"
          data-testid="repository-sync-status-glyph"
        >
          <SyncGlyph indicator={indicator} />
        </span>
        {indicator === "failing" && (
          <Pulse
            tone="danger"
            className="right-[6.5px] bottom-[6.5px]"
            data-testid="repository-sync-status-pulse"
          />
        )}
      </LinkButton>
    </Tooltip>
  );
}
