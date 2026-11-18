import { ChevronRightIcon } from "lucide-react";
import { Button, Disclosure, DisclosurePanel } from "react-aria-components";

import { DateDisplay } from "@/shared/components/display/date-display";
import { classNames } from "@/shared/utils/common";

import type { RepositoryLastRun } from "@/entities/repository/domain/model/repository-activity";
import { countBranchOutcomes } from "@/entities/repository/domain/rules/count-branch-outcomes";
import { IconMarker } from "@/entities/repository/ui/repository-activity-card/activity-markers";
import { LastRunRow } from "@/entities/repository/ui/repository-activity-card/last-run-row";
import { getOperationLabel } from "@/entities/repository/ui/repository-activity-card/repository-activity.view";

export function RepositoryLastRuns({ runs }: { runs: RepositoryLastRun[] }) {
  const [latest] = runs;

  if (!latest) {
    return (
      <p className="flex h-10 items-center border-t pr-3 pl-7.5 text-foreground-muted text-xs">
        No finished run recorded
      </p>
    );
  }

  const latestFailed = countBranchOutcomes(latest.branches).failed;

  return (
    <Disclosure className="border-t">
      {({ isExpanded }) => (
        <>
          <Button
            slot="trigger"
            className="flex h-10 w-full min-w-0 items-center gap-2.5 px-3 text-left text-xs hover:bg-content-strong/60 focus-visible:outline-2 focus-visible:outline-ring focus-visible:-outline-offset-2"
          >
            <IconMarker>
              <ChevronRightIcon
                className={classNames(
                  "size-3.5 shrink-0 transition-transform duration-150 ease-out motion-reduce:transition-none",
                  isExpanded && "rotate-90"
                )}
              />
            </IconMarker>
            <span className="shrink-0 font-medium">Last runs</span>
            {!isExpanded && (
              <span className="min-w-0 truncate text-foreground-muted">
                <span aria-hidden className="pr-1.5 text-foreground-muted/60">
                  ·
                </span>
                Latest: {getOperationLabel(latest.operation)} finished{" "}
                <DateDisplay
                  date={latest.finishedAt}
                  fullTimestamp
                  containerClassName="inline-flex shrink-0"
                />
                {latestFailed > 0 && <span className="text-danger">, {latestFailed} failed</span>}
              </span>
            )}
          </Button>
          <DisclosurePanel>
            <ul className="pb-1.5">
              {runs.map((run) => (
                <LastRunRow key={run.operation} run={run} />
              ))}
            </ul>
          </DisclosurePanel>
        </>
      )}
    </Disclosure>
  );
}
