import { Badge } from "@/components/ui/badge";
import { getProposedChangesDiffSummary } from "@/graphql/queries/proposed-changes/getProposedChangesDiffSummary";
import useQuery from "@/hooks/useQuery";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import ErrorScreen from "../errors/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";

type tProposedChangesData = {
  branch: string;
};

export const ProposedChangesData = ({ branch }: tProposedChangesData) => {
  const query = gql`
    ${getProposedChangesDiffSummary}
  `;

  const {
    loading,
    error,
    // data = {},
  } = useQuery(query, {
    variables: { branch },
    skip: true,
  });

  if (error) {
    return <ErrorScreen message="An error occured while fetching diff summary." />;
  }

  return (
    <div className="flex gap-2">
      <Badge className="rounded-full" variant="green">
        <Icon icon="mdi:plus-circle-outline" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : "1"}
      </Badge>

      <Badge className="rounded-full" variant="red">
        <Icon icon="mdi:minus-circle-outline" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : "1"}
      </Badge>

      <Badge className="rounded-full" variant="blue">
        <Icon icon="mdi:circle-arrows" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : "1"}
      </Badge>

      <Badge className="rounded-full" variant="yellow">
        <Icon icon="mdi:warning-outline" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : "1"}
      </Badge>
    </div>
  );
};
