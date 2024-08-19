import { getProposedChangesDiffSummary } from "@/graphql/queries/proposed-changes/getProposedChangesDiffSummary";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "../errors/error-screen";
import { BadgeAdd, BadgeConflict, BadgeRemove, BadgeUpdate } from "../diff/ui/badge";

export type DiffFilter = {
  namespace?: {
    excludes?: String[];
    includes?: String[];
  };
};

type tProposedChangesDiffSummary = {
  branch: string;
  filters: DiffFilter;
};

export const ProposedChangesDiffSummary = ({ branch, filters }: tProposedChangesDiffSummary) => {
  const {
    loading,
    error,
    data = {},
  } = useQuery(getProposedChangesDiffSummary, { skip: !branch, variables: { branch, filters } });

  if (error) {
    return <ErrorScreen message="An error occured while fetching diff summary." />;
  }

  return (
    <div className="flex gap-2">
      <BadgeAdd loading={!branch || loading}>{data?.DiffTreeSummary?.num_added}</BadgeAdd>
      <BadgeRemove loading={!branch || loading}>{data?.DiffTreeSummary?.num_removed}</BadgeRemove>
      <BadgeUpdate loading={!branch || loading}>{data?.DiffTreeSummary?.num_updated}</BadgeUpdate>
      <BadgeConflict loading={!branch || loading}>
        {data?.DiffTreeSummary?.num_conflicts}
      </BadgeConflict>
    </div>
  );
};
