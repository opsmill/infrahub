import {
  OperationVariables,
  useQuery as useApolloQuery,
  useLazyQuery as useApolloLazyQuery,
} from "@apollo/client";
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

export const useLazyQuery = (QUERY: any, options?: OperationVariables) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  return useApolloLazyQuery(QUERY, {
    context: { branch: branch?.name, date },
    ...options,
  });
};

export default useQuery;
