import ErrorScreen from "@/shared/components/errors/error-screen";
import { QSP } from "@/shared/config/qsp";

import { DIFF_STATUS } from "@/entities/diff/ui/node-diff/types";
import { useGetDiffSummary } from "@/entities/diff/ui/queries/get-diff-summary.query";
import { DiffSummarySkeleton } from "@/entities/proposed-changes/ui/diff-summary/diff-summary-skeleton";
import {
  DiffSummaryTag,
  DiffSummaryTagGroup,
} from "@/entities/proposed-changes/ui/diff-summary/diff-summary-tag-group";
import { getProposedChangeDetailsUrl } from "@/entities/proposed-changes/utils";

interface ProposedChangeDiffSummaryProps {
  branchName: string;
  proposedChangeId: string;
  className?: string;
}

export function ProposedChangeDiffSummary({
  proposedChangeId,
  branchName,
  className,
}: ProposedChangeDiffSummaryProps) {
  const { error, data, isPending } = useGetDiffSummary({ branch: branchName, proposedChangeId });

  if (isPending) {
    return <DiffSummarySkeleton />;
  }

  if (error) {
    return (
      <ErrorScreen
        message={error?.message ?? "No diff summary available."}
        hideIcon
        className="items-start p-0 text-gray-600 text-sm"
      />
    );
  }

  if (!data) {
    return null;
  }

  const dataTabUrl = (status: string) =>
    getProposedChangeDetailsUrl(proposedChangeId, "data", [{ name: QSP.STATUS, value: status }]);

  return (
    <DiffSummaryTagGroup className={className}>
      <DiffSummaryTag variant="added" count={data.num_added} href={dataTabUrl(DIFF_STATUS.ADDED)} />
      <DiffSummaryTag
        variant="removed"
        count={data.num_removed}
        href={dataTabUrl(DIFF_STATUS.REMOVED)}
      />
      <DiffSummaryTag
        variant="updated"
        count={data.num_updated}
        href={dataTabUrl(DIFF_STATUS.UPDATED)}
      />
      <DiffSummaryTag
        variant="conflicts"
        count={data.num_conflicts}
        href={dataTabUrl(DIFF_STATUS.CONFLICT)}
      />
    </DiffSummaryTagGroup>
  );
}
