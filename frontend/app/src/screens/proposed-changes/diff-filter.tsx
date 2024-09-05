import { getProposedChangesDiffSummary } from "@/graphql/queries/proposed-changes/getProposedChangesDiffSummary";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "../errors/error-screen";
import {
  BadgeAdded,
  BadgeConflict,
  BadgeRemoved,
  BadgeUpdated,
  CloseBadgeAdded,
  CloseBadgeConflict,
  CloseBadgeRemoved,
  CloseBadgeUpdated,
} from "../diff/diff-badge";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "@/config/qsp";
import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { classNames } from "@/utils/common";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";

export type DiffFilter = {
  namespace?: {
    excludes?: String[];
    includes?: String[];
  };
  status?: {
    excludes?: String[];
    includes?: String[];
  };
};

type ProposedChangeDiffFilterProps = {
  branch: string;
  filters?: DiffFilter;
};

export const diffActions = {
  ADDED: "ADDED",
  REMOVED: "REMOVED",
  UPDATED: "UPDATED",
  CONFLICT: "CONFLICT",
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
      <div className="flex justify-start">
        <ErrorScreen
          message={error?.message ?? "No diff summary available."}
          hideIcon
          className="p-0"
        />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 shrink-0">
      <FilterButton
        onClick={() => handleFilter(diffActions.ADDED)}
        muted={!!qsp && qsp !== diffActions.ADDED}
        disabled={!data?.DiffTreeSummary?.num_added && qsp !== diffActions.ADDED}
        className="relative">
        <BadgeAdded>{data?.DiffTreeSummary?.num_added}</BadgeAdded>
        {qsp === diffActions.ADDED && <CloseBadgeAdded />}
      </FilterButton>

      <FilterButton
        onClick={() => handleFilter(diffActions.REMOVED)}
        muted={!!qsp && qsp !== diffActions.REMOVED}
        disabled={!data?.DiffTreeSummary?.num_removed && qsp !== diffActions.REMOVED}
        className="relative">
        <BadgeRemoved>{data?.DiffTreeSummary?.num_removed}</BadgeRemoved>
        {qsp === diffActions.REMOVED && <CloseBadgeRemoved />}
      </FilterButton>

      <FilterButton
        onClick={() => handleFilter(diffActions.UPDATED)}
        muted={!!qsp && qsp !== diffActions.UPDATED}
        disabled={!data?.DiffTreeSummary?.num_updated && qsp !== diffActions.UPDATED}
        className="relative">
        <BadgeUpdated>{data?.DiffTreeSummary?.num_updated}</BadgeUpdated>
        {qsp === diffActions.UPDATED && <CloseBadgeUpdated />}
      </FilterButton>

      <FilterButton
        onClick={() => handleFilter(diffActions.CONFLICT)}
        muted={!!qsp && qsp !== diffActions.CONFLICT}
        disabled={!data?.DiffTreeSummary?.num_conflicts && qsp !== diffActions.CONFLICT}
        className="relative">
        <BadgeConflict>{data?.DiffTreeSummary?.num_conflicts}</BadgeConflict>
        {qsp === diffActions.CONFLICT && <CloseBadgeConflict />}
      </FilterButton>
    </div>
  );
};

export const FilterButton = ({ muted, children, ...props }: ButtonProps & { muted?: boolean }) => (
  <Button
    {...props}
    variant="ghost"
    className={classNames("relative rounded-full p-0 h-auto", muted && "opacity-60")}>
    {children}
  </Button>
);
