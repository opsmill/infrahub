import { useGetDiffSummary } from "@/entities/diff/ui/queries/get-diff-summary.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";
import { getProposedChangeDetailsUrl } from "@/entities/proposed-changes/utils";

export interface SchemaTabProps {
  sourceBranch: string;
  proposedChangeId: string;
}

export function SchemaTab({ sourceBranch, proposedChangeId }: SchemaTabProps) {
  const { isPending, data, error } = useGetDiffSummary({
    branch: sourceBranch,
    proposedChangeId,
    filters: {
      namespace: { includes: ["Schema"], excludes: ["Profile"] },
      status: { excludes: ["UNCHANGED"] },
    },
  });

  const count = !error && data ? data.num_added + data.num_updated + data.num_removed : undefined;

  return (
    <ProposedChangeTab
      to={getProposedChangeDetailsUrl(proposedChangeId, "schema")}
      label="Schema"
      count={count}
      isCountLoading={isPending}
    />
  );
}
