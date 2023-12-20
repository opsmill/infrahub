import { OperationVariables, useQuery as useApolloQuery } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { currentBranchAtom } from "../state/atoms/branches.atom";
import { datetimeAtom } from "../state/atoms/time.atom";

const useQuery = (QUERY: any, options?: OperationVariables) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  return useApolloQuery(QUERY, {
    ...options,
    context: { branch: branch?.name, date },
  });
};

export default useQuery;
