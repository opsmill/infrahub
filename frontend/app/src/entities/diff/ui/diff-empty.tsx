import { DiffRefreshButton } from "@/entities/diff/ui/diff-refresh-button";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { formatFullDate, formatRelativeTimeFromNow } from "@/shared/utils/date";
import { Icon } from "@iconify-icon/react";

export interface DiffEmptyProps {
  branchName: string;
  lastRefreshedAt: Date;
}

export function DiffEmpty({ branchName, lastRefreshedAt }: DiffEmptyProps) {
  return (
    <div className="flex flex-col items-center my-10 gap-5">
      <div className="p-3 rounded-full bg-white inline-flex">
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
        <p>If you have made any changes, please refresh the diff:</p>
      </div>

      <DiffRefreshButton branchName={branchName} />
    </div>
  );
}
