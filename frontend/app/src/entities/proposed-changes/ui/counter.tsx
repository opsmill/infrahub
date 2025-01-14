import useQuery from "@/shared/api/graphql/useQuery";
import LoadingScreen from "@/shared/components/loading-screen";
import { Badge } from "@/shared/components/ui/badge";
import { gql } from "@apollo/client";

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
