import useQuery from "@/shared/api/graphql/useQuery";
import { Badge } from "@/shared/components/ui/badge";
import { Spinner } from "@/shared/components/ui/spinner";
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
        <Spinner />
      </Badge>
    );
  }

  if (!data) {
    return <Badge className="rounded-full">0</Badge>;
  }

  return <Badge className="rounded-full">{data[kind].count}</Badge>;
};
