import { useMutation } from "@tanstack/react-query";
import { Icon } from "@iconify-icon/react";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { installFromMarketplace } from "@/entities/schema-marketplace/api/marketplace.queries";
import { useInstallTaskStatus } from "@/entities/schema-marketplace/hooks/use-install-task-status";
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

type TaskLinkTone = "default" | "success" | "danger";

function TaskLink({ taskId, tone = "default" }: { taskId: string; tone?: TaskLinkTone }) {
  const toneClass =
    tone === "success"
      ? "text-green-800 hover:text-green-900"
      : tone === "danger"
        ? "text-red-700 hover:text-red-900"
        : "text-gray-500 hover:text-custom-blue-700";
  return (
    <Link
      to={`/tasks/${taskId}`}
      className={classNames("flex items-center gap-0.5 whitespace-nowrap text-xs hover:underline", toneClass)}
    >
      View task
      <Icon icon="mdi:open-in-new" className="text-[10px]" />
    </Link>
  );
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

  // The target toggle above already picks the install method visually;
  // the icon here only reinforces it (lightning = direct install, source-
  // branch = git commit path). Badge label removed — it was competing for
  // horizontal space with the branch name and truncating it. The helper
  // text below spells out what the branch actually means per target.
  const isDirect = target === "direct";
  const branchIcon = isDirect ? "mdi:lightning-bolt" : "mdi:source-branch";
  const editable = allowOverride && branchEdited;

  return (
    <>
      <label className="text-sm" htmlFor={inputId}>
        Branch
      </label>
      {!editable ? (
        // Keep this field readable at the 320px sidebar width: icon + branch
        // name + Override button only. The "Tracking" state and the target
        // meaning are both covered by the helper line below.
        <div className="flex items-center justify-between gap-2 rounded-md border border-gray-200 bg-gray-50 px-2 py-1.5 text-sm">
          <div className="flex min-w-0 flex-1 items-center gap-1.5">
            <Icon icon={branchIcon} className="shrink-0 text-gray-500" />
            <span className="min-w-0 truncate font-mono">{branchName}</span>
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

  // Each effect below owns exactly one derived bit of state and reads/writes
  // a disjoint set — no shared writes, no interleaving order dependency.
  // They're intentionally kept as three small effects rather than collapsed
  // into a single reducer because the lifecycles differ:
  //   1. `branchName` follows the top-bar branch (external prop).
  //   2. `repositoryId` seeds from the query result (external fetch).
  //   3. `target` falls back to "direct" when the derived capability vanishes.

  useEffect(() => {
    // 1. When the user switches the top-bar Infrahub branch, retarget the
    //    install. A manual Override (branchEdited=true) takes precedence.
    if (!branchEdited) {
      setBranchName(currentBranch.name);
    }
  }, [currentBranch.name, branchEdited]);

  useEffect(() => {
    // 2. When writable repositories load (or the current selection disappears
    //    because the user deleted the repo in another tab), default to the
    //    first one. Does not touch branchName — the top-bar branch wins over
    //    `default_branch` as the install target.
    const first = writableRepositories[0];
    if (!first) return;
    const stillValid = writableRepositories.some((r) => r.id === repositoryId);
    if (!stillValid) {
      setRepositoryId(first.id);
    }
  }, [writableRepositories, repositoryId]);

  useEffect(() => {
    // 3. Fall back to direct when the repository target becomes unavailable:
    //    writable repos disappeared, or the user switched to a non-synced
    //    Infrahub branch. Repository installs without git sync would leave
    //    an orphaned Git branch not mapped to any Infrahub branch.
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

  // Poll the workflow's task until it reaches a terminal state. Only active
  // while we have a task_id and the drawer hasn't moved to completed/failed
  // — the hook's own refetchInterval also stops on terminal server states.
  const pollingTaskId =
    state.phase === "pending" || state.phase === "running" ? state.taskId : null;
  const taskStatus = useInstallTaskStatus(pollingTaskId);

  useEffect(() => {
    if (!pollingTaskId) return;
    const snapshot = taskStatus.data;
    if (!snapshot || !snapshot.found) return;
    if (snapshot.state === "RUNNING" || snapshot.state === "PENDING" || snapshot.state === "SCHEDULED") {
      setState({ phase: "running", taskId: pollingTaskId, progress: snapshot.progress });
      return;
    }
    if (snapshot.state === "COMPLETED") {
      setState({ phase: "completed", taskId: pollingTaskId });
      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Schema install completed" />, {
        toastId: `marketplace-install-${pollingTaskId}-success`,
      });
      return;
    }
    if (snapshot.state === "FAILED" || snapshot.state === "CRASHED" || snapshot.state === "CANCELLED") {
      const reason = snapshot.state.toLowerCase();
      setState({
        phase: "failed",
        taskId: pollingTaskId,
        error: `Task ${reason} — check the Tasks page for details.`,
      });
      toast(
        <Alert type={ALERT_TYPES.ERROR} message={`Schema install ${reason}`} />,
        { toastId: `marketplace-install-${pollingTaskId}-fail` }
      );
    }
  }, [pollingTaskId, taskStatus.data]);

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
        <h2 className="font-semibold">Install</h2>
        {selection.length > 0 && (
          <Badge variant="blue">
            {selection.length} selected
          </Badge>
        )}
      </header>

      {selection.length === 0 ? (
        <div className="flex flex-col items-center gap-1 rounded-md border border-gray-200 border-dashed p-4 text-center">
          <Icon icon="mdi:cursor-default-click-outline" className="text-gray-400 text-xl" />
          <p className="text-gray-500 text-sm">Nothing selected yet</p>
          <p className="text-gray-400 text-xs">
            Click a schema or collection to add it to the install.
          </p>
        </div>
      ) : (
        // Cap the selection list so a large batch doesn't push the install
        // button below the fold inside the sidebar. Scrolls inside the card.
        <ul className="-mr-1 flex max-h-64 flex-col gap-1 overflow-auto pr-1">
          {selection.map((item) => (
            <li
              key={itemKey(item)}
              className="flex items-center justify-between gap-2 rounded-md border border-gray-200 px-2 py-1 text-sm"
            >
              <div className="flex min-w-0 items-center gap-1.5">
                <Icon
                  icon={item.kind === "collection" ? "mdi:package-variant-closed" : "mdi:file-code"}
                  className="shrink-0 text-gray-500"
                />
                <span className="truncate font-mono text-xs">
                  {item.namespace}/{item.name}
                </span>
                {item.semver && (
                  <Badge variant="lightgray-outline" className="shrink-0">
                    v{item.semver}
                  </Badge>
                )}
              </div>
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
          <details className="group rounded-md border border-blue-200 bg-blue-50 text-custom-blue-700 text-xs">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 p-2 font-semibold">
              <Icon
                icon="mdi:chevron-right"
                className="transition-transform group-open:rotate-90"
              />
              Direct install skips Git — why it matters
            </summary>
            <p className="px-2 pb-2 pl-7">
              Schemas are applied to this instance immediately, with no commit or version history.
              If you plan to edit them later via proposed changes, install into a writable Git
              repository instead so the YAML is tracked.
            </p>
          </details>
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
        <div className="flex items-center justify-between gap-2 text-gray-500 text-sm">
          <span className="flex items-center gap-1.5">
            <Icon icon="mdi:loading" className="animate-spin" />
            Queued — waiting for worker
          </span>
          <TaskLink taskId={state.taskId} />
        </div>
      )}
      {state.phase === "running" && (
        <div className="flex items-center justify-between gap-2 text-gray-500 text-sm">
          <span className="flex items-center gap-1.5">
            <Icon icon="mdi:loading" className="animate-spin" />
            Installing{typeof state.progress === "number" ? ` (${state.progress}%)` : "…"}
          </span>
          <TaskLink taskId={state.taskId} />
        </div>
      )}
      {state.phase === "completed" && (
        <div className="rounded-md bg-green-50 p-3 text-green-800 text-sm">
          <div className="flex items-center justify-between gap-2">
            <p className="flex items-center gap-1.5 font-semibold">
              <Icon icon="mdi:check-circle" /> Install completed
            </p>
            <TaskLink taskId={state.taskId} tone="success" />
          </div>
        </div>
      )}
      {state.phase === "failed" && (
        <div className="rounded-md bg-red-50 p-3 text-red-700 text-sm">
          <div className="flex items-center justify-between gap-2">
            <p className="font-semibold">Install failed</p>
            {state.taskId && <TaskLink taskId={state.taskId} tone="danger" />}
          </div>
          <p className="mt-1">{state.error}</p>
        </div>
      )}
    </Card>
  );
}
