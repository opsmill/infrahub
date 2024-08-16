import { Badge } from "@/components/ui/badge";
import useQuery from "@/hooks/useQuery";
import { Icon } from "@iconify-icon/react";
import ErrorScreen from "../errors/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { getProposedChangesDiffSummary } from "@/graphql/queries/proposed-changes/getProposedChangesDiffSummary";

type tProposedChangesDiffSummary = {
  branch: string;
};

export const ProposedChangesDiffSummary = ({ branch }: tProposedChangesDiffSummary) => {
  const {
    loading,
    error,
    data = {},
  } = useQuery(getProposedChangesDiffSummary, { variables: { branch } });

  if (error) {
    return <ErrorScreen message="An error occured while fetching diff summary." />;
  }

  return (
    <div className="flex gap-2">
      <Badge className="rounded-full" variant="green">
        <Icon icon="mdi:plus-circle-outline" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : data.DiffTreeSummary.num_added}
      </Badge>

      <Badge className="rounded-full" variant="red">
        <Icon icon="mdi:minus-circle-outline" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : data.DiffTreeSummary.num_removed}
      </Badge>

      <Badge className="rounded-full" variant="blue">
        <Icon icon="mdi:circle-arrows" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : data.DiffTreeSummary.num_updated}
      </Badge>

      {/* <Badge className="rounded-full" variant="yellow">
        <Icon icon="mdi:warning-outline" className="text-xs mr-1" />
        {loading ? <LoadingScreen size={8} hideText /> : data.DiffTreeSummary.num_conflicts}
      </Badge> */}
    </div>
  );
};
