import { getProposedChangesDiffSummary } from "@/graphql/queries/proposed-changes/getProposedChangesDiffSummary";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "../errors/error-screen";
import { BadgeAdded, BadgeConflict, BadgeRemoved, BadgeUpdated } from "./badge";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "@/config/qsp";
import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { classNames } from "@/utils/common";

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

type tProposedChangesDiffSummary = {
  branch: string;
  filters: DiffFilter;
};

export const diffActions = {
  ADDED: "ADDED",
  REMOVED: "REMOVED",
  UPDATED: "UPDATED",
  CONFLICT: "CONFLICT",
};

export const ProposedChangesDiffSummary = ({ branch, filters }: tProposedChangesDiffSummary) => {
  const [qsp, setQsp] = useQueryParam(QSP.STATUS, StringParam);

  const {
    loading,
    error,
    data = {},
  } = useQuery(getProposedChangesDiffSummary, {
    skip: !branch,
    variables: { branch, filters },
  });

  const handleFilter = (value: string) => {
    // Removes filter
    if (value === qsp) return setQsp(undefined);

    // Set filter
    setQsp(value);
  };

  if (error) {
    return <ErrorScreen message="An error occured while fetching diff summary." />;
  }

  return (
    <div className="flex items-center gap-2 shrink-0">
      <FilterButton
        onClick={() => handleFilter(diffActions.ADDED)}
        muted={!!qsp && qsp !== diffActions.ADDED}>
        <BadgeAdded>{data?.DiffTreeSummary?.num_added}</BadgeAdded>
      </FilterButton>

      <FilterButton
        onClick={() => handleFilter(diffActions.REMOVED)}
        muted={!!qsp && qsp !== diffActions.REMOVED}>
        <BadgeRemoved>{data?.DiffTreeSummary?.num_removed}</BadgeRemoved>
      </FilterButton>

      <FilterButton
        onClick={() => handleFilter(diffActions.UPDATED)}
        muted={!!qsp && qsp !== diffActions.UPDATED}>
        <BadgeUpdated>{data?.DiffTreeSummary?.num_updated}</BadgeUpdated>
      </FilterButton>

      <FilterButton
        onClick={() => handleFilter(diffActions.CONFLICT)}
        muted={!!qsp && qsp !== diffActions.CONFLICT}>
        <BadgeConflict>{data?.DiffTreeSummary?.num_conflicts}</BadgeConflict>
      </FilterButton>
    </div>
  );
};

export const FilterButton = ({ muted, ...props }: ButtonProps & { muted?: boolean }) => (
  <Button
    {...props}
    variant="ghost"
    className={classNames("rounded-full p-0 h-auto", muted && "opacity-60")}
  />
);
