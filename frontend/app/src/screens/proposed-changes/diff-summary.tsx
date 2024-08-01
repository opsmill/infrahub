import { Badge } from "@/components/ui/badge";
import { getProposedChangesDiffSummary } from "@/graphql/queries/proposed-changes/getProposedChangesDiffSummary";
import useQuery from "@/hooks/useQuery";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import ErrorScreen from "../errors/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";

type tProposedChangesDiffSummary = {
  branch: string;
};

export const ProposedChangesDiffSummary = ({ branch }: tProposedChangesDiffSummary) => {
  const query = gql`
    ${getProposedChangesDiffSummary}
  `;

  const {
    loading,
    error,
    data = {},
  } = useQuery(query, {
    branch,
  });

  if (error) {
    return <ErrorScreen message="An error occured while fetching diff summary." />;
  }

  const summary = data?.DiffSummary?.map((node) => {
    return node?.elements?.map((element) => {
      return element?.summary;
    });
  })
    .flat()
    .reduce(
      (acc, sum) => {
        return {
          added: acc.added + sum.added,
          removed: acc.removed + sum.removed,
          updated: acc.updated + sum.updated,
          conflicts: acc.conflicts + sum.conflicts,
        };
      },
      { added: 0, removed: 0, updated: 0, conflicts: 0 }
    );

  return (
    <div className="flex gap-2">
      <Badge className="rounded-full" variant="green">
        <Icon icon="mdi:plus-circle-outline" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : summary.added || "-"}
      </Badge>

      <Badge className="rounded-full" variant="red">
        <Icon icon="mdi:minus-circle-outline" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : summary.removed || "-"}
      </Badge>

      <Badge className="rounded-full" variant="blue">
        <Icon icon="mdi:circle-arrows" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : summary.updated || "-"}
      </Badge>

      {/* <Badge className="rounded-full" variant="yellow">
        <Icon icon="mdi:warning-outline" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : summary.added}
      </Badge> */}
    </div>
  );
};
