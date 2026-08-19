import { useGetDiffSummary } from "@/entities/diff/ui/queries/get-diff-summary.query";
import { getProposedChangeDetailsUrl } from "@/entities/proposed-changes/ui/routing/proposed-change-urls";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface DataTabProps {
  sourceBranch: string;
  proposedChangeId: string;
}

export function DataTab({ sourceBranch, proposedChangeId }: DataTabProps) {
  const { isPending, data, error } = useGetDiffSummary({
    branch: sourceBranch,
    proposedChangeId,
    filters: {
      namespace: { excludes: ["Schema"] },
      status: { excludes: ["UNCHANGED"] },
    },
  });

  const count = !error && data ? data.num_added + data.num_updated + data.num_removed : undefined;

  return (
    <ProposedChangeTab
      to={getProposedChangeDetailsUrl(proposedChangeId, "data")}
      label="Data"
      count={count}
      isCountLoading={isPending}
    />
  );
}
