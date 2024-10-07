import React from "react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { QSP } from "@/config/qsp";
import { getProposedChangesDiffSummary } from "@/graphql/queries/proposed-changes/getProposedChangesDiffSummary";
import useQuery from "@/hooks/useQuery";
import { DiffBadge } from "@/screens/diff/node-diff/utils";
import ErrorScreen from "@/screens/errors/error-screen";
import { constructPath } from "@/utils/fetch";
import { DIFF_STATUS, DiffStatus } from "../diff/node-diff/types";

interface DiffTreeSummary {
  num_added: number;
  num_removed: number;
  num_updated: number;
  num_conflicts: number;
}

interface ProposedChangeDiffSummaryProps {
  branchName: string;
  proposedChangeId: string;
}

const BadgeLink: React.FC<{
  status: DiffStatus;
  count: number | undefined;
  proposedChangeId: string;
}> = ({ status, count, proposedChangeId }) => {
  const proposedChangeDetailsPath = `/proposed-changes/${proposedChangeId}`;
  const tabSearchParam = { name: QSP.PROPOSED_CHANGES_TAB, value: "data" };

  return (
    <Link
      to={constructPath(proposedChangeDetailsPath, [
        tabSearchParam,
        { name: QSP.STATUS, value: status },
      ])}
    >
      <DiffBadge status={status}>{count}</DiffBadge>
    </Link>
  );
};

export const ProposedChangeDiffSummary: React.FC<ProposedChangeDiffSummaryProps> = ({
  proposedChangeId,
  branchName,
}) => {
  const { error, data, loading } = useQuery<{ DiffTreeSummary: DiffTreeSummary }>(
    getProposedChangesDiffSummary,
    {
      skip: !branchName,
      variables: { branch: branchName },
      context: {
        processErrorMessage: (message: string) => {
          if (!message.includes("not found")) {
            toast(<Alert type={ALERT_TYPES.ERROR} message={message} />, {
              toastId: "alert-error",
            });
          }
        },
      },
    }
  );

  if (loading) {
    return <DiffSummarySkeleton />;
  }

  if (error) {
    return (
      <ErrorScreen
        message={error?.message ?? "No diff summary available."}
        hideIcon
        className="p-0 items-start"
      />
    );
  }

  const { DiffTreeSummary } = data || {};

  return (
    <div className="inline-flex gap-2">
      <BadgeLink
        status={DIFF_STATUS.ADDED}
        count={DiffTreeSummary?.num_added}
        proposedChangeId={proposedChangeId}
      />
      <BadgeLink
        status={DIFF_STATUS.REMOVED}
        count={DiffTreeSummary?.num_removed}
        proposedChangeId={proposedChangeId}
      />
      <BadgeLink
        status={DIFF_STATUS.UPDATED}
        count={DiffTreeSummary?.num_updated}
        proposedChangeId={proposedChangeId}
      />
      <BadgeLink
        status={DIFF_STATUS.CONFLICT}
        count={DiffTreeSummary?.num_conflicts}
        proposedChangeId={proposedChangeId}
      />
    </div>
  );
};

const DiffSummarySkeleton: React.FC = () => {
  return (
    <div className="flex gap-2">
      {[...Array(4)].map((_, index) => (
        <div key={index} className="h-6 w-9 bg-gray-200 animate-pulse rounded-full" />
      ))}
    </div>
  );
};
