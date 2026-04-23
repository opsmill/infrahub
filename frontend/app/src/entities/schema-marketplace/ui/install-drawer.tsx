import { useMutation } from "@tanstack/react-query";
import { Icon } from "@iconify-icon/react";
import { useMemo, useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";

import { installFromMarketplace } from "@/entities/schema-marketplace/api/marketplace.queries";
import type { WritableRepositorySummary } from "@/entities/schema-marketplace/hooks/use-writable-repositories";
import type {
  InstallDrawerState,
  MarketplaceInstallItem,
} from "@/entities/schema-marketplace/types";

interface InstallDrawerProps {
  selection: MarketplaceInstallItem[];
  writableRepositories: WritableRepositorySummary[];
  className?: string;
  onRemove?: (item: MarketplaceInstallItem) => void;
}

function itemLabel(item: MarketplaceInstallItem): string {
  const version = item.semver ? ` @${item.semver}` : "";
  return `${item.kind}: ${item.namespace}/${item.name}${version}`;
}

function itemKey(item: MarketplaceInstallItem): string {
  return `${item.kind}:${item.namespace}/${item.name}@${item.semver ?? "latest"}`;
}

export function InstallDrawer({
  selection,
  writableRepositories,
  className,
  onRemove,
}: InstallDrawerProps) {
  const defaultRepoId = writableRepositories[0]?.id ?? "";
  const [repositoryId, setRepositoryId] = useState<string>(defaultRepoId);
  const [branchName, setBranchName] = useState<string>(() => {
    return writableRepositories[0]?.default_branch ?? "main";
  });
  const [state, setState] = useState<InstallDrawerState>({ phase: "idle" });

  const selectedRepo = useMemo(
    () => writableRepositories.find((r) => r.id === repositoryId),
    [writableRepositories, repositoryId]
  );

  const mutation = useMutation({
    mutationFn: () =>
      installFromMarketplace({
        repository_id: repositoryId,
        branch_name: branchName,
        items: selection,
      }),
    onMutate: () => setState({ phase: "submitting" }),
    onSuccess: (data) => setState({ phase: "pending", taskId: data.task_id }),
    onError: (err: Error) =>
      setState({ phase: "failed", taskId: "", error: err.message || "Install failed" }),
  });

  const canInstall =
    selection.length > 0 && writableRepositories.length > 0 && !!repositoryId && !!branchName;

  return (
    <Card className={classNames("flex flex-col gap-3", className)}>
      <header className="flex items-center justify-between gap-2">
        <h2 className="font-semibold">Install selected</h2>
        <Badge variant="gray-outline">{selection.length} selected</Badge>
      </header>

      {selection.length === 0 && (
        <p className="text-gray-500 text-sm">
          Pick one or more schemas or collections to install.
        </p>
      )}

      {selection.length > 0 && (
        <ul className="flex flex-col gap-1">
          {selection.map((item) => (
            <li
              key={itemKey(item)}
              className="flex items-center justify-between gap-2 rounded-md border border-gray-200 px-2 py-1 text-sm"
            >
              <span className="truncate font-mono">{itemLabel(item)}</span>
              {onRemove && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove ${item.namespace}/${item.name}`}
                  onClick={() => onRemove(item)}
                >
                  <Icon icon="mdi:close" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {writableRepositories.length > 0 && (
        <div className="flex flex-col gap-2">
          <label className="text-sm" htmlFor="schema-marketplace-target-repo">
            Target repository
          </label>
          <select
            id="schema-marketplace-target-repo"
            className="rounded-md border border-gray-200 p-2 text-sm"
            value={repositoryId}
            onChange={(event) => {
              const next = event.target.value;
              setRepositoryId(next);
              const repo = writableRepositories.find((r) => r.id === next);
              setBranchName(repo?.default_branch ?? "main");
            }}
          >
            {writableRepositories.map((repo) => (
              <option key={repo.id} value={repo.id}>
                {repo.name}
              </option>
            ))}
          </select>

          <label className="text-sm" htmlFor="schema-marketplace-target-branch">
            Branch
          </label>
          <input
            id="schema-marketplace-target-branch"
            className="rounded-md border border-gray-200 p-2 text-sm"
            type="text"
            value={branchName}
            onChange={(event) => setBranchName(event.target.value)}
            placeholder={selectedRepo?.default_branch ?? "main"}
          />
        </div>
      )}

      <Button
        type="button"
        variant="primary"
        disabled={!canInstall || state.phase === "submitting"}
        onClick={() => mutation.mutate()}
      >
        {state.phase === "submitting" ? "Queuing install…" : "Install to repository"}
      </Button>

      {state.phase === "pending" && (
        <p className="text-gray-500 text-sm">
          Queued as task <span className="font-mono">{state.taskId}</span>. Check the Tasks page
          for progress.
        </p>
      )}
      {state.phase === "failed" && (
        <div className="rounded-md bg-red-50 p-3 text-red-700 text-sm">
          <p className="mb-1 font-semibold">Install failed</p>
          <p>{state.error}</p>
        </div>
      )}
    </Card>
  );
}
