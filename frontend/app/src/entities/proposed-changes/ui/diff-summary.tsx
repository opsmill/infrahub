import { useQuery } from "@apollo/client";
import type React from "react";
import { Link } from "react-router";
import { toast } from "react-toastify";

import { QSP } from "@/config/qsp";

import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { DiffBadge } from "@/entities/diff/node-diff/utils";
import { getProposedChangesDiffSummary } from "@/entities/proposed-changes/api/getProposedChangesDiffSummary";

import { DIFF_STATUS, type DiffStatus } from "../../diff/node-diff/types";

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
      data-testid={`diff-${status.toLowerCase()}-count`}
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
        className="items-start p-0"
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
        <div key={index} className="h-6 w-9 animate-pulse rounded-full bg-gray-200" />
      ))}
    </div>
  );
};
