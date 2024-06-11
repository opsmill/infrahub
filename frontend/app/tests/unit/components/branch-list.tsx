import { gql } from "@apollo/client";
import useQuery from "../../../src/hooks/useQuery";

export const QUERY = gql`
  query {
    Branch {
      name
      origin_branch
      branched_from
      created_at
      sync_with_git
      description
    }
  }
`;

const Apollo = () => {
  const { loading, error, data } = useQuery(QUERY);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!data || error) {
    return <div>Error</div>;
  }

  return <div>Working!</div>;
};

export default Apollo;
