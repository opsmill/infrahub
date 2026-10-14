import { ChevronRightIcon } from "lucide-react";
import React from "react";

import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import { getBranchDetailsUrl } from "@/entities/branches/ui/routing/branch-urls";
import type {
  RepositoryLastRun,
  RepositoryRunBranchOutcome,
} from "@/entities/repository/domain/model/repository-activity";
import { DotMarker } from "@/entities/repository/ui/repository-activity-card/activity-markers";
import { ActivityTime } from "@/entities/repository/ui/repository-activity-card/activity-values";
import {
  getOperationLabel,
  getRunOutcomeParts,
} from "@/entities/repository/ui/repository-activity-card/repository-activity.view";

const ROW = "flex h-9 w-full min-w-0 items-center gap-2.5 px-3 text-left text-sm";

function RunSummary({ run, isOpen }: { run: RepositoryLastRun; isOpen?: boolean }) {
  const { failed, changed } = getRunOutcomeParts(run);

  return (
    <>
      <DotMarker tone={failed ? "danger" : "neutral"} />
      <span className="shrink-0 font-medium">{getOperationLabel(run.operation)}</span>
      <span className="flex min-w-0 items-center gap-1.5 truncate tabular-nums">
        {failed && <span className="truncate text-danger">{failed}</span>}
        {failed && changed && (
          <span aria-hidden className="text-foreground-muted/60">
            ·
          </span>
        )}
        {changed && <span className="truncate text-foreground-muted">{changed}</span>}
        {!failed && !changed && <span className="text-foreground-muted">No change</span>}
      </span>
      {isOpen !== undefined && (
        <ChevronRightIcon
          aria-hidden
          className={classNames(
            "size-3.5 shrink-0 text-foreground-muted transition-transform duration-150 ease-out motion-reduce:transition-none",
            isOpen && "rotate-90"
          )}
        />
      )}
      <span className="ml-auto pl-3 text-xs">
        <ActivityTime date={run.finishedAt} />
      </span>
    </>
  );
}

function BranchLinks({
  label,
  branches,
  className,
}: {
  label: string;
  branches: RepositoryRunBranchOutcome[];
  className: string;
}) {
  if (branches.length === 0) return null;

  return (
    <div className="flex min-w-0 gap-3">
      <span className={classNames("w-16 shrink-0", className)}>{label}</span>
      <ul className="flex min-w-0 flex-wrap gap-x-3 gap-y-0.5">
        {branches.map(({ branchName }) => (
          <li key={branchName} className="min-w-0">
            <Link
              to={getBranchDetailsUrl(branchName)}
              className="block truncate no-underline decoration-solid hover:underline"
            >
              {branchName}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function LastRunRow({ run }: { run: RepositoryLastRun }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const panelId = React.useId();

  if (run.branches.length <= 1) {
    return (
      <li className={ROW}>
        <RunSummary run={run} />
      </li>
    );
  }

  return (
    <li>
      <button
        type="button"
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={() => setIsOpen((open) => !open)}
        className={classNames(
          ROW,
          "hover:bg-content-strong/60 focus-visible:outline-2 focus-visible:outline-ring focus-visible:-outline-offset-2"
        )}
      >
        <RunSummary run={run} isOpen={isOpen} />
      </button>
      {isOpen && (
        <div id={panelId} className="flex flex-col gap-1 pt-0.5 pr-3 pb-2.5 pl-7.5 text-sm">
          <BranchLinks
            label="Failed"
            branches={run.branches.filter(({ outcome }) => outcome === "FAILED")}
            className="text-danger"
          />
          <BranchLinks
            label="Changed"
            branches={run.branches.filter(({ outcome }) => outcome === "IMPORTED")}
            className="text-foreground-muted"
          />
        </div>
      )}
    </li>
  );
}
