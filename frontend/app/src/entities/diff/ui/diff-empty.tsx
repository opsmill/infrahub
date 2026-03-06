import { Icon } from "@iconify-icon/react";

import { Tooltip } from "@/shared/components/ui/tooltip";
import { formatFullDate, formatRelativeTimeFromNow } from "@/shared/utils/date";

import { DiffRefreshButton } from "@/entities/diff/ui/diff-refresh-button";

export interface DiffEmptyProps {
  branchName: string;
  lastRefreshedAt: Date;
  branchExists?: boolean;
  hideActions?: boolean;
}

export function DiffEmpty({
  branchName,
  lastRefreshedAt,
  branchExists = true,
  hideActions,
}: DiffEmptyProps) {
  return (
    <div className="my-10 flex flex-col items-center gap-5">
      <div className="inline-flex rounded-full bg-white p-3">
        <Icon icon="mdi:circle-off-outline" className="text-2xl text-custom-blue-800" />
      </div>

      <h1 className="font-semibold text-lg">No changes detected</h1>
      <div className="text-center">
        <p>
          The last comparison was made{" "}
          <Tooltip enabled content={formatFullDate(lastRefreshedAt)}>
            <span className="font-semibold">{formatRelativeTimeFromNow(lastRefreshedAt)}</span>
          </Tooltip>
          .
        </p>
        {branchExists && !hideActions && (
          <p>If you have made any changes, please refresh the diff:</p>
        )}
      </div>

      {branchExists && !hideActions && <DiffRefreshButton branchName={branchName} />}
    </div>
  );
}
