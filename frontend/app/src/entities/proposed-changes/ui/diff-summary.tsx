import type React from "react";
import { Link } from "react-router";

import { QSP } from "@/config/qsp";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";

import { useGetDiffSummary } from "@/entities/diff/domain/get-diff-summary.query";
import { DIFF_STATUS, type DiffStatus } from "@/entities/diff/node-diff/types";
import { DiffBadge } from "@/entities/diff/node-diff/utils";

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

  return (
    <Link
      to={constructPath(proposedChangeDetailsPath, [
        { name: QSP.PROPOSED_CHANGES_TAB, value: "data" },
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
  const { error, data, isPending } = useGetDiffSummary({ branchName });

  if (isPending) {
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

  if (!data) {
    return null;
  }

  return (
    <Row>
      <BadgeLink
        status={DIFF_STATUS.ADDED}
        count={data.num_added}
        proposedChangeId={proposedChangeId}
      />
      <BadgeLink
        status={DIFF_STATUS.REMOVED}
        count={data.num_removed}
        proposedChangeId={proposedChangeId}
      />
      <BadgeLink
        status={DIFF_STATUS.UPDATED}
        count={data.num_updated}
        proposedChangeId={proposedChangeId}
      />
      <BadgeLink
        status={DIFF_STATUS.CONFLICT}
        count={data.num_conflicts}
        proposedChangeId={proposedChangeId}
      />
    </Row>
  );
};

const DiffSummarySkeleton: React.FC = () => {
  return (
    <Row>
      {[...Array(4)].map((_, index) => (
        <div key={index} className="h-6 w-9 animate-pulse rounded-full bg-gray-200" />
      ))}
    </Row>
  );
};
