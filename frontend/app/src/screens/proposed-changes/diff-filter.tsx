import { getProposedChangesDiffSummary } from "@/graphql/queries/proposed-changes/getProposedChangesDiffSummary";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "../errors/error-screen";

import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "@/config/qsp";
import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { classNames } from "@/utils/common";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { DIFF_STATUS } from "@/screens/diff/node-diff/types";
import { DiffBadge } from "@/screens/diff/node-diff/utils";
import {
  CloseBadgeAdded,
  CloseBadgeConflict,
  CloseBadgeRemoved,
  CloseBadgeUpdated,
} from "@/screens/diff/diff-badge";

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
  const [qsp, setQsp] = useQueryParam(QSP.STATUS, StringParam);

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
    // Removes filter
    if (value === qsp) return setQsp(undefined);

    // Set filter
    setQsp(value);
  };

  if (error) {
    return (
      <ErrorScreen
        message={error?.message ?? "No diff summary available."}
        hideIcon
        className="p-0 items-start"
      />
    );
  }

  return (
    <div className="flex items-center gap-2 shrink-0">
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
      className={classNames("relative rounded-full p-0 h-auto", isMuted && "opacity-60")}
      onClick={() => onFilter(status)}
      disabled={isDisabled}
    >
      <DiffBadge status={status}>{count}</DiffBadge>
      {currentFilter === status && CloseBadge && <CloseBadge />}
    </Button>
  );
};
