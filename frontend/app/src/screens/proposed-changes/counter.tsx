import { Badge } from "@/components/ui/badge";
import useQuery from "@/hooks/useQuery";
import { gql } from "@apollo/client";
import LoadingScreen from "../loading-screen/loading-screen";

type tProposedChangesCounter = {
  query: string;
  id: string;
  kind: string;
};

export const ProposedChangesCounter = ({ query, id, kind }: tProposedChangesCounter) => {
  const { loading, data = {} } = useQuery(
    gql`
      ${query}
    `,
    {
      variables: { id },
      skip: !id,
      notifyOnNetworkStatusChange: true,
    }
  );

  if (loading) {
    return (
      <Badge className="rounded-full">
        <LoadingScreen size={8} hideText />
      </Badge>
    );
  }

  if (!data) {
    return <Badge className="rounded-full">0</Badge>;
  }

  return <Badge className="rounded-full">{data[kind].count}</Badge>;
};
