import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { QSP } from "@/shared/config/qsp";

import { useGetDiffSummary } from "@/entities/diff/domain/get-diff-summary.query";
import { DIFF_STATUS } from "@/entities/diff/node-diff/types";
import { DiffSummarySkeleton } from "@/entities/proposed-changes/ui/diff-summary/diff-summary-skeleton";
import {
  DiffSummaryTag,
  DiffSummaryTagGroup,
} from "@/entities/proposed-changes/ui/diff-summary/diff-summary-tag-group";

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

  const proposedChangeDetailsPath = `/proposed-changes/${proposedChangeId}`;

  return (
    <DiffSummaryTagGroup className={className}>
      <DiffSummaryTag
        variant="added"
        count={data.num_added}
        href={constructPath(proposedChangeDetailsPath, [
          { name: QSP.PROPOSED_CHANGES_TAB, value: "data" },
          { name: QSP.STATUS, value: DIFF_STATUS.ADDED },
        ])}
      />
      <DiffSummaryTag
        variant="removed"
        count={data.num_removed}
        href={constructPath(proposedChangeDetailsPath, [
          { name: QSP.PROPOSED_CHANGES_TAB, value: "data" },
          { name: QSP.STATUS, value: DIFF_STATUS.REMOVED },
        ])}
      />
      <DiffSummaryTag
        variant="updated"
        count={data.num_updated}
        href={constructPath(proposedChangeDetailsPath, [
          { name: QSP.PROPOSED_CHANGES_TAB, value: "data" },
          { name: QSP.STATUS, value: DIFF_STATUS.UPDATED },
        ])}
      />
      <DiffSummaryTag
        variant="conflicts"
        count={data.num_conflicts}
        href={constructPath(proposedChangeDetailsPath, [
          { name: QSP.PROPOSED_CHANGES_TAB, value: "data" },
          { name: QSP.STATUS, value: DIFF_STATUS.CONFLICT },
        ])}
      />
    </DiffSummaryTagGroup>
  );
}
