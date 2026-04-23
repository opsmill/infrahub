import { useMutation } from "@tanstack/react-query";
import { Icon } from "@iconify-icon/react";
import { useEffect, useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { installFromMarketplace } from "@/entities/schema-marketplace/api/marketplace.queries";
import type { WritableRepositorySummary } from "@/entities/schema-marketplace/hooks/use-writable-repositories";
import type {
  InstallDrawerState,
  MarketplaceInstallItem,
  MarketplaceInstallTarget,
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

interface BranchFieldProps {
  branchName: string;
  currentBranchName: string;
  branchEdited: boolean;
  setBranchName: (value: string) => void;
  setBranchEdited: (value: boolean) => void;
  inputId: string;
  placeholder: string;
  target: MarketplaceInstallTarget;
  /**
   * Whether the user can override the tracked branch with a freeform name.
   * - direct target: true -- any Infrahub branch is valid to schema-load against.
   * - repository target: false -- the install method toggle already gates to
   *   git-synced branches, so allowing freeform here would re-open the
   *   orphaned-Git-branch foot-gun we're trying to avoid.
   */
  allowOverride: boolean;
}

function BranchField({
  branchName,
  currentBranchName,
  branchEdited,
  setBranchName,
  setBranchEdited,
  inputId,
  placeholder,
  target,
  allowOverride,
}: BranchFieldProps) {
  // If override was previously engaged and is now disallowed (e.g. user
  // flipped target back to repository), fall back to tracking.
  useEffect(() => {
    if (!allowOverride && branchEdited) {
      setBranchEdited(false);
      setBranchName(currentBranchName);
    }
  }, [allowOverride, branchEdited, currentBranchName, setBranchEdited, setBranchName]);

  const reset = () => {
    setBranchEdited(false);
    setBranchName(currentBranchName);
  };

  // Icon + badge semantics differ per target:
  //  - direct target: the branch is an Infrahub branch, not a Git branch -- the
  //    Git source-branch icon would be misleading, so we use the lightning
  //    icon matching the Direct toggle and label it "Infrahub branch".
  //  - repository target: show the Git source-branch icon and a "Git branch"
  //    badge. A "(will create if missing)" hint is shown in the helper line
  //    since we can't currently detect existence client-side; the backend
  //    auto-creates from default_branch if absent.
  const isDirect = target === "direct";
  const branchIcon = isDirect ? "mdi:lightning-bolt" : "mdi:source-branch";
  const badgeLabel = isDirect ? "Infrahub branch" : "Git branch";
  const editable = allowOverride && branchEdited;

  return (
    <>
      <label className="text-sm" htmlFor={inputId}>
        Branch
      </label>
      {!editable ? (
        <div className="flex items-center justify-between gap-2 rounded-md border border-gray-200 bg-gray-50 px-2 py-1.5 text-sm">
          <div className="flex items-center gap-1.5 truncate">
            <Icon icon={branchIcon} className="text-gray-500" />
            <span className="truncate font-mono">{branchName}</span>
            <Badge variant="lightgray-outline">{badgeLabel}</Badge>
            <Badge variant="lightgray-outline">Tracking</Badge>
          </div>
          {allowOverride && (
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={() => setBranchEdited(true)}
              aria-label="Override branch"
            >
              <Icon icon="mdi:pencil" className="mr-1" /> Override
            </Button>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <Icon icon={branchIcon} className="text-gray-500" />
          <input
            id={inputId}
            className="flex-1 rounded-md border border-gray-200 p-2 text-sm"
            type="text"
            value={branchName}
            onChange={(event) => setBranchName(event.target.value)}
            placeholder={placeholder}
          />
          <Button
            type="button"
            variant="ghost"
            size="xs"
            onClick={reset}
            aria-label="Reset to current Infrahub branch"
          >
            <Icon icon="mdi:refresh" className="mr-1" /> Reset
          </Button>
        </div>
      )}
      {!editable ? (
        <p className="text-gray-500 text-xs">
          Tracks the Infrahub branch from the top bar.
          {isDirect
            ? " Switch branches up there and this updates."
            : " Repository installs are limited to git-synced branches; switch branches up top to retarget."}
        </p>
      ) : (
        <p className="text-gray-500 text-xs">
          Custom Infrahub branch. Reset to track the top bar again.
        </p>
      )}
    </>
  );
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
  const hasWritableRepo = writableRepositories.length > 0;
  const { currentBranch } = useCurrentBranch();
  const currentBranchSynced = currentBranch.sync_with_git === true;
  const canUseRepositoryTarget = hasWritableRepo && currentBranchSynced;

  const [target, setTarget] = useState<MarketplaceInstallTarget>(
    canUseRepositoryTarget ? "repository" : "direct"
  );
  const [repositoryId, setRepositoryId] = useState<string>("");
  const [branchName, setBranchName] = useState<string>(currentBranch.name);
  const [branchEdited, setBranchEdited] = useState(false);
  const [state, setState] = useState<InstallDrawerState>({ phase: "idle" });

  // Track the top-bar Infrahub branch: whenever the user switches branches,
  // retarget the install unless they've already edited the field manually.
  useEffect(() => {
    if (!branchEdited) {
      setBranchName(currentBranch.name);
    }
  }, [currentBranch.name, branchEdited]);

  // Once writable repositories load (or change), default the repo selection
  // to the first one. Do NOT override branchName here -- the top-bar branch
  // takes precedence over the repo's default_branch.
  useEffect(() => {
    const first = writableRepositories[0];
    if (!first) return;
    const stillValid = writableRepositories.some((r) => r.id === repositoryId);
    if (!stillValid) {
      setRepositoryId(first.id);
    }
  }, [writableRepositories, repositoryId]);

  // Fall back to direct when the repository target becomes unavailable:
  //  - writable repos disappear (rare), OR
  //  - user switches the top-bar to an Infrahub branch without git sync.
  // Repository installs without git sync would leave an orphaned Git branch
  // not mapped to any Infrahub branch, so we gate the UI here.
  useEffect(() => {
    if (!canUseRepositoryTarget && target === "repository") {
      setTarget("direct");
    }
  }, [canUseRepositoryTarget, target]);

  // React Compiler memoizes derived values like this automatically — see
  // dev/knowledge/frontend/react.md. No manual useMemo needed.
  const selectedRepo = writableRepositories.find((r) => r.id === repositoryId);

  const mutation = useMutation({
    mutationFn: () =>
      installFromMarketplace({
        target,
        repository_id: target === "repository" ? repositoryId : null,
        branch_name: branchName,
        items: selection,
      }),
    onMutate: () => setState({ phase: "submitting" }),
    onSuccess: (data) => setState({ phase: "pending", taskId: data.task_id }),
    onError: (err: Error) =>
      setState({ phase: "failed", taskId: "", error: err.message || "Install failed" }),
  });

  const canInstall =
    selection.length > 0 &&
    !!branchName &&
    (target === "direct" || (hasWritableRepo && !!repositoryId));

  const primaryLabel =
    state.phase === "submitting"
      ? "Queuing install…"
      : target === "repository"
        ? "Install to repository"
        : "Install directly to Infrahub";

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

      <div className="flex flex-col gap-2">
        <span className="text-sm">Install method</span>
        <div className="flex rounded-md border border-gray-200 p-0.5">
          <Button
            type="button"
            variant={target === "repository" ? "primary" : "ghost"}
            size="sm"
            className="flex-1"
            disabled={!canUseRepositoryTarget}
            onClick={() => setTarget("repository")}
            aria-pressed={target === "repository"}
            aria-describedby={
              !canUseRepositoryTarget ? "schema-marketplace-repo-disabled-reason" : undefined
            }
          >
            <Icon icon="mdi:git" className="mr-1" /> To repository
          </Button>
          <Button
            type="button"
            variant={target === "direct" ? "primary" : "ghost"}
            size="sm"
            className="flex-1"
            onClick={() => setTarget("direct")}
            aria-pressed={target === "direct"}
          >
            <Icon icon="mdi:lightning-bolt" className="mr-1" /> Direct
          </Button>
        </div>
        {!canUseRepositoryTarget && hasWritableRepo && !currentBranchSynced && (
          <div
            id="schema-marketplace-repo-disabled-reason"
            className="rounded-md bg-yellow-50 p-2 text-yellow-800 text-xs"
          >
            <p className="mb-0.5 font-semibold">
              "To repository" requires a git-synced Infrahub branch
            </p>
            <p>
              The current branch <span className="font-mono">{currentBranch.name}</span> has no Git
              sync, so committing to a repository would leave an orphaned Git branch. Switch to a
              branch created with <strong>Sync with Git</strong> enabled, or use Direct install.
            </p>
          </div>
        )}
        {target === "direct" && (
          <div className="rounded-md bg-blue-50 p-2 text-custom-blue-700 text-xs">
            <p className="mb-0.5 font-semibold">Recommended: connect a writable Git repository</p>
            <p>
              Direct install applies schemas to Infrahub immediately without a Git commit. If you
              plan to edit these schemas later via proposed changes, install into a writable
              repository instead so the YAML is version-controlled.
            </p>
          </div>
        )}
      </div>

      {target === "repository" && hasWritableRepo && (
        <div className="flex flex-col gap-2">
          <label className="text-sm" htmlFor="schema-marketplace-target-repo">
            Target repository
          </label>
          <select
            id="schema-marketplace-target-repo"
            className="rounded-md border border-gray-200 p-2 text-sm"
            value={repositoryId}
            onChange={(event) => setRepositoryId(event.target.value)}
          >
            {writableRepositories.map((repo) => (
              <option key={repo.id} value={repo.id}>
                {repo.name}
              </option>
            ))}
          </select>

          <BranchField
            branchName={branchName}
            currentBranchName={currentBranch.name}
            branchEdited={branchEdited}
            setBranchName={setBranchName}
            setBranchEdited={setBranchEdited}
            inputId="schema-marketplace-target-branch"
            placeholder={selectedRepo?.default_branch ?? currentBranch.name}
            target={target}
            allowOverride={false}
          />
        </div>
      )}

      {target === "direct" && (
        <div className="flex flex-col gap-2">
          <BranchField
            branchName={branchName}
            currentBranchName={currentBranch.name}
            branchEdited={branchEdited}
            setBranchName={setBranchName}
            setBranchEdited={setBranchEdited}
            inputId="schema-marketplace-direct-branch"
            placeholder={currentBranch.name}
            target={target}
            allowOverride={true}
          />
        </div>
      )}

      <Button
        type="button"
        variant="primary"
        disabled={!canInstall || state.phase === "submitting"}
        onClick={() => mutation.mutate()}
      >
        {primaryLabel}
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
