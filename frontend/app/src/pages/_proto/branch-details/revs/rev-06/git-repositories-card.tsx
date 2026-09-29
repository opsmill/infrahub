// PROTOTYPE — the IFC-3200 "Git repositories" card (canvas section 4), without the Upstream and
// Last import columns, which have no backend field yet.
import { Button, Card, CardHeader, Menu, MenuItem, MenuTrigger, Popover } from "@infrahub/ui";
import {
  AlertCircleIcon,
  AlertTriangleIcon,
  EllipsisVerticalIcon,
  FolderGitIcon,
  GitCommitIcon,
  LockIcon,
  RefreshCwIcon,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "react-toastify";

import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { classNames, getTextColor } from "@/shared/utils/common";

import { GIT_STATE, OPERATIONAL_ERROR, type ProtoData, type Repo } from "./data";
import { bandDomId, type LocateTarget, useLocate } from "./locate";
import {
  CELL_HEIGHT_PX,
  clampPage,
  getTotalPages,
  PAGE_SIZE,
  TablePagination,
} from "./table-pagination";

const TASK_HREF = "/tasks";

export function GitRepositoriesCard({
  data,
  page,
  onPageChange,
  maxBands,
  refreshedAt,
  isRefreshing,
  onRefresh,
  locate,
  objectStyle = false,
}: {
  objectStyle?: boolean;
  locate: LocateTarget | null;
  onLocate: (target: Omit<LocateTarget, "nonce">) => void;
  refreshedAt: Date;
  isRefreshing: boolean;
  onRefresh: () => void;
  data: ProtoData;
  page: number;
  onPageChange: (page: number) => void;
  maxBands: number;
}) {
  const [showAllBands, setShowAllBands] = useState(false);
  const rank = (r: Repo) =>
    r.gitState === "import-error" ? 2 : OPERATIONAL_ERROR[r.operational] ? 1 : 0;
  const sorted = [...data.repos].sort((a, b) => rank(b) - rank(a));
  // Failing repositories sort first. In the real card this is server-side ordering, not a client sort.
  const totalPages = getTotalPages(sorted.length, PAGE_SIZE);
  const currentPage = clampPage(page, totalPages);
  const rows = sorted.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const failing = sorted.filter((r) => rank(r) > 0);
  const bands = showAllBands ? failing : failing.slice(0, maxBands);

  useLocate(locate, "band", (repoId) => {
    const index = failing.findIndex((r) => r.id === repoId);
    if (index < 0) return null;
    if (index >= maxBands) setShowAllBands(true);
    return bandDomId(repoId);
  });

  return (
    <Card className="overflow-hidden p-0">
      {objectStyle ? (
        <CardHeader className="flex items-center gap-2">
          <h2>Git repositories</h2>
          {data.status === "ok" && (
            <Badge variant="blue" className="rounded-full font-normal tabular-nums">
              {data.repos.length}
            </Badge>
          )}
        </CardHeader>
      ) : (
        <header className="flex items-center gap-2 px-4 py-3">
          <h2 className="font-semibold text-sm">Git repositories</h2>
          {data.status === "ok" && (
            <span className="rounded-full bg-neutral-100 px-1.5 text-neutral-600 text-xs tabular-nums">
              {data.repos.length}
            </span>
          )}
          <span
            className="ml-auto flex items-center gap-1 text-neutral-500 text-xs"
            aria-live="polite"
          >
            {isRefreshing ? (
              "Refreshing…"
            ) : (
              <>
                Updated <DateDisplay date={refreshedAt} />
              </>
            )}
          </span>
          <Button
            variant="ghost"
            size="sm"
            shape="square"
            aria-label="Refresh repositories and merge readiness"
            isDisabled={isRefreshing}
            onPress={onRefresh}
          >
            <RefreshCwIcon
              aria-hidden
              className={classNames(
                "size-4 text-neutral-500",
                isRefreshing && "animate-spin motion-reduce:animate-none"
              )}
            />
          </Button>
        </header>
      )}

      {data.status === "loading" && <SkeletonRows />}

      {data.status === "denied" && (
        <div className="flex items-start gap-2 border-neutral-200 border-t px-4 py-4 text-neutral-700 text-sm">
          <LockIcon className="mt-0.5 size-4 shrink-0 text-neutral-500" aria-hidden />
          <div>
            <div className="font-medium">You don't have access to this branch's repositories</div>
            <p className="text-neutral-600">
              Ask an administrator for read access to repositories on all branches to see their Git
              state here.
            </p>
          </div>
        </div>
      )}

      {data.status === "ok" && data.repos.length === 0 && (
        <div className="border-neutral-200 border-t px-4 py-6 text-center text-sm">
          <div className="font-medium text-neutral-800">Not synchronised with Git</div>
          <p className="mx-auto mt-1 max-w-prose text-pretty text-neutral-600">
            This branch was created in Infrahub with Sync with Git off, so no repository imports or
            generators run on it.
          </p>
        </div>
      )}

      {data.status === "ok" && data.repos.length > 0 && (
        <>
          <div
            className="overflow-x-auto"
            style={totalPages > 1 ? { minHeight: (PAGE_SIZE + 1) * CELL_HEIGHT_PX } : undefined}
          >
            <table className="w-full min-w-[560px] table-fixed text-sm">
              <thead className="bg-neutral-50 text-left text-neutral-600">
                <tr className="border-neutral-200 border-y">
                  <Th icon={<FolderGitIcon className="size-3.5" />}>Repository</Th>
                  <Th className="w-[124px]">Git state</Th>
                  <Th
                    className="w-[176px] bg-[#e9f7fa]"
                    icon={<GitCommitIcon className="size-3.5 text-[#087895]" />}
                  >
                    Commit
                  </Th>
                  <th className="w-10">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((repo) => (
                  <RepoRow key={repo.id} repo={repo} />
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <TablePagination
              className="border-neutral-200 border-t"
              page={currentPage}
              pageSize={PAGE_SIZE}
              totalCount={sorted.length}
              onPageChange={onPageChange}
            />
          )}

          {bands.map((r) =>
            r.importError ? (
              <ImportErrorBand
                key={r.id}
                repo={r}
                message={r.importError.message}
                taskId={r.importError.taskId}
              />
            ) : (
              <UnreachableBand key={r.id} repo={r} />
            )
          )}
          {failing.length > maxBands && (
            <div className="flex items-center justify-between gap-2 border-red-200 border-t bg-red-50 px-4 py-2 text-red-900 text-xs">
              <span className="tabular-nums">
                {showAllBands
                  ? `${failing.length} repositories with errors`
                  : `${failing.length - maxBands} more ${failing.length - maxBands > 1 ? "repositories" : "repository"} with errors: ${failing
                      .slice(maxBands)
                      .map((r) => r.name)
                      .join(", ")}`}
              </span>
              <Button variant="ghost" size="xs" onPress={() => setShowAllBands((v) => !v)}>
                {showAllBands ? "Collapse" : "Show all"}
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  );
}

function Th({
  children,
  className,
  icon,
}: {
  children: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}) {
  return (
    <th className={classNames("h-10 px-3 font-medium text-xs", className)}>
      <span className="flex items-center gap-1.5">
        {icon && <span aria-hidden>{icon}</span>}
        {children}
      </span>
    </th>
  );
}

function GitStatePill({ state }: { state: Repo["gitState"] }) {
  const { label, color } = GIT_STATE[state];
  return (
    <span
      className="inline-flex whitespace-nowrap rounded-md px-2 py-0.5 text-xs"
      style={{ backgroundColor: color, color: getTextColor(color) }}
    >
      {label}
    </span>
  );
}

function RepoRow({ repo }: { repo: Repo }) {
  const failed = repo.gitState === "import-error";
  const unreachable = OPERATIONAL_ERROR[repo.operational];
  const info = (m: string) => toast(<Alert type={ALERT_TYPES.INFO} message={`${m} (prototype)`} />);

  return (
    <tr className="h-10 border-neutral-200 border-b last:border-b-0">
      <td className="px-3">
        <div className="flex min-w-0 items-center gap-1.5">
          <FolderGitIcon className="size-3.5 shrink-0 text-neutral-500" aria-hidden />
          <a href={`/objects/CoreRepository/${repo.id}`} title={repo.name} className="truncate">
            {repo.name}
          </a>
          {repo.readOnly && (
            <span className="shrink-0 rounded bg-neutral-100 px-1 text-neutral-600 text-xs">
              Read-only
            </span>
          )}
        </div>
      </td>
      <td className={classNames("px-3", failed && "bg-[#fff5f5]")}>
        <span className="flex items-center gap-1.5">
          <GitStatePill state={repo.gitState} />
          {unreachable && (
            <AlertTriangleIcon
              className="size-3.5 shrink-0 text-amber-700"
              aria-label={unreachable}
            />
          )}
        </span>
      </td>
      <td className="bg-[#e9f7fa] px-3 font-mono text-[13px] tabular-nums">
        <span className="block truncate" title={repo.commit}>
          {repo.commit}
        </span>
      </td>
      <td className="px-1 text-center">
        <MenuTrigger>
          <Button
            variant="ghost"
            size="xs"
            shape="square"
            className="relative before:absolute before:-inset-1.5"
            aria-label={`Actions for ${repo.name}`}
          >
            <EllipsisVerticalIcon className="size-4 text-neutral-500" />
          </Button>
          <Popover placement="bottom end">
            <Menu>
              <MenuItem href={`/objects/CoreRepository/${repo.id}`}>Open repository</MenuItem>
              <MenuItem href={TASK_HREF}>View tasks</MenuItem>
              <MenuItem onAction={() => info("Reimport last commit")}>
                Reimport last commit
              </MenuItem>
            </Menu>
          </Popover>
        </MenuTrigger>
      </td>
    </tr>
  );
}

function ImportErrorBand({
  repo,
  message,
  taskId,
}: {
  repo: Repo;
  message: string;
  taskId: string;
}) {
  return (
    <div
      id={bandDomId(repo.id)}
      tabIndex={-1}
      className="flex scroll-mt-4 items-start gap-2.5 border-red-200 border-t bg-red-50 px-4 py-3 outline-offset-[-2px]"
    >
      <AlertCircleIcon className="mt-0.5 size-4 shrink-0 text-red-700" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="font-semibold text-[13px] text-red-900">
          <span className="break-all">{repo.name}</span> — import failed
        </div>
        <p className="whitespace-pre-wrap break-words font-mono text-red-800 text-xs leading-relaxed">
          {message}
        </p>
      </div>
      <Link
        to={constructPath(`/tasks/${taskId}`)}
        className="shrink-0 px-2 py-1 font-medium text-red-800 text-xs hover:underline"
      >
        View task log →
      </Link>
    </div>
  );
}

function UnreachableBand({ repo }: { repo: Repo }) {
  return (
    <div
      id={bandDomId(repo.id)}
      tabIndex={-1}
      className="flex scroll-mt-4 items-start gap-2.5 border-amber-200 border-t bg-amber-50 px-4 py-3 outline-offset-[-2px]"
    >
      <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-amber-700" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="font-semibold text-[13px] text-amber-900">
          <span className="break-all">{repo.name}</span> — {OPERATIONAL_ERROR[repo.operational]}
        </div>
        <p className="text-amber-800 text-xs leading-relaxed">
          Infrahub can't fetch new commits, so the commit shown may be out of date. Check the
          repository's credentials and location.
        </p>
      </div>
      <a
        href={`/objects/CoreRepository/${repo.id}`}
        className="shrink-0 px-2 py-1 font-medium text-amber-900 text-xs"
      >
        Open repository
      </a>
    </div>
  );
}

function SkeletonRows() {
  return (
    <div role="status" aria-busy="true" className="border-neutral-200 border-t">
      <span className="sr-only">Loading repositories</span>
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex h-10 items-center gap-4 border-neutral-100 border-b px-3">
          <div className="h-3 w-[34%] animate-pulse rounded bg-neutral-200 motion-reduce:animate-none" />
          <div className="h-4 w-16 animate-pulse rounded bg-neutral-200 motion-reduce:animate-none" />
          <div className="h-3 w-14 animate-pulse rounded bg-neutral-200 motion-reduce:animate-none" />
        </div>
      ))}
    </div>
  );
}
