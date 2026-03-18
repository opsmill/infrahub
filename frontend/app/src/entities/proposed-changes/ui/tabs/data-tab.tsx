import { DIFF_TABS } from "@/shared/config/constants";

import { useGetDiffSummary } from "@/entities/diff/domain/get-diff-summary.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface DataTabProps {
  sourceBranch: string;
  proposedChangeId?: string;
}

export function DataTab({ sourceBranch, proposedChangeId }: DataTabProps) {
  const { isPending, data, error } = useGetDiffSummary({
    branch: sourceBranch,
    proposedChangeId,
    filters: {
      namespace: { excludes: ["Schema", "Profile"] },
      status: { excludes: ["UNCHANGED"] },
    },
  });

  const count = !error && data ? data.num_added + data.num_updated + data.num_removed : undefined;

  return (
    <ProposedChangeTab
      tabId={DIFF_TABS.DATA}
      label="Data"
      count={count}
      isCountLoading={isPending}
    />
  );
}
