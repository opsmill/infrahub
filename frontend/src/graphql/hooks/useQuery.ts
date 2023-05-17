import { useQuery as useApolloQuery, useReactiveVar } from "@apollo/client";
import { branchVar } from "../variables/branchVar";
import { dateVar } from "../variables/dateVar";

const useQuery = (QUERY: any, options?: any) => {
  const branch = useReactiveVar(branchVar);
  console.log("USE QUERY branch: ", branch);
  const date = useReactiveVar(dateVar);

  return useApolloQuery(QUERY, { ...options, context: { branch: branch?.name, date } });
};

export default useQuery;
