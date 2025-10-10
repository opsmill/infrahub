import { useQuery } from "@apollo/client";
import { parseAsString, useQueryState } from "nuqs";
import { toast } from "react-toastify";

import { QSP } from "@/config/qsp";

import { Button, type ButtonProps } from "@/shared/components/buttons/button-primitive";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";

import { DIFF_STATUS } from "@/entities/diff/node-diff/types";
import { DiffBadge } from "@/entities/diff/node-diff/utils";
import {
  CloseBadgeAdded,
  CloseBadgeConflict,
  CloseBadgeRemoved,
  CloseBadgeUpdated,
} from "@/entities/diff/ui/diff-badge";
import { getProposedChangesDiffSummary } from "@/entities/proposed-changes/api/getProposedChangesDiffSummary";

export type DiffFilter = {
  namespace?: {
    excludes?: string[];
    includes?: string[];
  };
  status?: {
    excludes?: string[];
    includes?: string[];
  };
};

type ProposedChangeDiffFilterProps = {
  branch: string;
  filters?: DiffFilter;
};

export const ProposedChangeDiffFilter = ({ branch, filters }: ProposedChangeDiffFilterProps) => {
  const [qsp, setQsp] = useQueryState(QSP.STATUS, parseAsString.withOptions({ shallow: false }));

  const { error, data = {} } = useQuery(getProposedChangesDiffSummary, {
    skip: !branch,
    variables: { branch, filters },
    context: {
      processErrorMessage: (message: string) => {
        // If the branch is not found, then do not display alert
        if (message.includes("not found")) return;

        toast(<Alert type={ALERT_TYPES.ERROR} message={message} />, {
          toastId: "alert-error",
        });
      },
    },
  });

  const handleFilter = (value: string) => {
    setQsp(value === qsp ? null : value);
  };

  if (error) {
    return (
      <ErrorScreen
        message={error?.message ?? "No diff summary available."}
        hideIcon
        className="items-start p-0"
      />
    );
  }

  return (
    <div className="flex shrink-0 items-center gap-2">
      <FilterButton
        status={DIFF_STATUS.ADDED}
        count={data?.DiffTreeSummary?.num_added}
        currentFilter={qsp}
        onFilter={handleFilter}
      />
      <FilterButton
        status={DIFF_STATUS.REMOVED}
        count={data?.DiffTreeSummary?.num_removed}
        currentFilter={qsp}
        onFilter={handleFilter}
      />
      <FilterButton
        status={DIFF_STATUS.UPDATED}
        count={data?.DiffTreeSummary?.num_updated}
        currentFilter={qsp}
        onFilter={handleFilter}
      />
      <FilterButton
        status={DIFF_STATUS.CONFLICT}
        count={data?.DiffTreeSummary?.num_conflicts}
        currentFilter={qsp}
        onFilter={handleFilter}
      />
    </div>
  );
};

interface FilterButtonProps extends ButtonProps {
  status: string;
  count: number;
  currentFilter: string | null | undefined;
  onFilter: (value: string) => void;
}

const FilterButton = ({ status, count, currentFilter, onFilter, ...props }: FilterButtonProps) => {
  const isMuted = !!currentFilter && currentFilter !== status;
  const isDisabled = !count && currentFilter !== status;

  const CloseBadge =
    status === DIFF_STATUS.ADDED
      ? CloseBadgeAdded
      : status === DIFF_STATUS.REMOVED
        ? CloseBadgeRemoved
        : status === DIFF_STATUS.UPDATED
          ? CloseBadgeUpdated
          : status === DIFF_STATUS.CONFLICT
            ? CloseBadgeConflict
            : null;

  return (
    <Button
      {...props}
      variant="ghost"
      className={classNames("relative h-auto rounded-full p-0", isMuted && "opacity-60")}
      onClick={() => onFilter(status)}
      disabled={isDisabled}
      data-testid={`diff-filters-button-${status.toLowerCase()}`}
    >
      <DiffBadge status={status}>{count}</DiffBadge>
      {currentFilter === status && CloseBadge && <CloseBadge />}
    </Button>
  );
};
