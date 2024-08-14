import { getProposedChangesDiffSummary } from "@/graphql/queries/proposed-changes/getProposedChangesDiffSummary";
import useQuery from "@/hooks/useQuery";
import { gql } from "@apollo/client";
import ErrorScreen from "../errors/error-screen";
import { BadgeAdd, BadgeConflict, BadgeRemove, BadgeUpdate } from "../diff/ui/badge";

type tProposedChangesDiffSummary = {
  branch: string;
};

export const ProposedChangesDiffSummary = ({ branch }: tProposedChangesDiffSummary) => {
  const query = gql`
    ${getProposedChangesDiffSummary}
  `;

  const { loading, error, data = {} } = useQuery(query, { skip: !branch, variables: { branch } });

  if (error) {
    return <ErrorScreen message="An error occured while fetching diff summary." />;
  }

  return (
    <div className="flex gap-2">
      <BadgeAdd loading={!branch || loading}>{data?.DiffTree?.num_added}</BadgeAdd>
      <BadgeRemove loading={!branch || loading}>{data?.DiffTree?.num_removed}</BadgeRemove>
      <BadgeUpdate loading={!branch || loading}>{data?.DiffTree?.num_updated}</BadgeUpdate>
      <BadgeConflict loading={!branch || loading}>{data?.DiffTree?.num_conflicts}</BadgeConflict>
    </div>
  );
};
