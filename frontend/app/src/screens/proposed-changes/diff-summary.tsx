import { getProposedChangesDiffSummary } from "@/graphql/queries/proposed-changes/getProposedChangesDiffSummary";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "../errors/error-screen";
import { BadgeAdd, BadgeConflict, BadgeRemove, BadgeUpdate } from "../diff/ui/badge";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "@/config/qsp";

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
    <div className="flex gap-2">
      <BadgeAdd
        loading={!branch || loading}
        onClick={() => handleFilter(diffActions.ADDED)}
        active={qsp === diffActions.ADDED}>
        {data?.DiffTreeSummary?.num_added}
      </BadgeAdd>
      <BadgeRemove
        loading={!branch || loading}
        onClick={() => handleFilter(diffActions.REMOVED)}
        active={qsp === diffActions.REMOVED}>
        {data?.DiffTreeSummary?.num_removed}
      </BadgeRemove>
      <BadgeUpdate
        loading={!branch || loading}
        onClick={() => handleFilter(diffActions.UPDATED)}
        active={qsp === diffActions.UPDATED}>
        {data?.DiffTreeSummary?.num_updated}
      </BadgeUpdate>
      <BadgeConflict
        loading={!branch || loading}
        onClick={() => handleFilter(diffActions.CONFLICT)}
        active={qsp === diffActions.CONFLICT}>
        {data?.DiffTreeSummary?.num_conflicts}
      </BadgeConflict>
    </div>
  );
};
