import { OperationVariables, useQuery as useApolloQuery, useReactiveVar } from "@apollo/client";
import { dateVar } from "../graphql/variables/dateVar";
import { useAtomValue } from "jotai/index";
import { currentBranchAtom } from "../state/atoms/branches.atom";

const useQuery = (QUERY: any, options?: OperationVariables) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useReactiveVar(dateVar);

  return useApolloQuery(QUERY, {
    ...options,
    context: { branch: branch?.name, date },
  });
};

export default useQuery;
