import { DIFF_TABS } from "@/shared/config/constants";

import { useGetDiffSummary } from "@/entities/diff/domain/get-diff-summary.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface DataTabProps {
  sourceBranch: string;
}

export function DataTab({ sourceBranch }: DataTabProps) {
  const { isPending, data } = useGetDiffSummary({
    branch: sourceBranch,
    filters: {
      namespace: { excludes: ["Schema", "Profile"] },
      status: { excludes: ["UNCHANGED"] },
    },
  });

  const count = (data?.num_added ?? 0) + (data?.num_updated ?? 0) + (data?.num_removed ?? 0);

  return (
    <ProposedChangeTab
      tabId={DIFF_TABS.DATA}
      label="Data"
      count={count}
      isCountLoading={isPending}
    />
  );
}
