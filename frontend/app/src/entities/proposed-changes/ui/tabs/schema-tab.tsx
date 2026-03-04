import { DIFF_TABS } from "@/shared/config/constants";

import { useGetDiffSummary } from "@/entities/diff/ui/queries/get-diff-summary.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface SchemaTabProps {
  sourceBranch: string;
}

export function SchemaTab({ sourceBranch }: SchemaTabProps) {
  const { isPending, data, error } = useGetDiffSummary({
    branch: sourceBranch,
    filters: {
      namespace: { includes: ["Schema"], excludes: ["Profile"] },
      status: { excludes: ["UNCHANGED"] },
    },
  });

  const count = !error && data ? data.num_added + data.num_updated + data.num_removed : undefined;

  return (
    <ProposedChangeTab
      tabId={DIFF_TABS.SCHEMA}
      label="Schema"
      count={count}
      isCountLoading={isPending}
    />
  );
}
