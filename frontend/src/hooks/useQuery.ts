import { useQuery as useApolloQuery, useReactiveVar } from "@apollo/client";
import { branchVar } from "../graphql/variables/branchVar";
import { dateVar } from "../graphql/variables/dateVar";

const useQuery = (QUERY: any, options?: any) => {
  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);

  return useApolloQuery(QUERY, { ...options, context: { branch: branch?.name, date } });
};

export default useQuery;
