import {
  type OperationVariables,
  useLazyQuery as useApolloLazyQuery,
  useMutation as useApolloMutation,
  useQuery as useApolloQuery,
} from "@apollo/client";
import { useAtomValue } from "jotai";

import { CONFIG } from "@/shared/config/config";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import usePagination from "../../hooks/usePagination";

interface Options extends OperationVariables {
  branch?: string;
  context?: Record<string, string | boolean | ((message: string) => void)>;
}

const useQuery: typeof useApolloQuery = (QUERY, options?: Options) => {
  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);
  const [{ offset, limit }] = usePagination();

  return useApolloQuery(QUERY, {
    ...options,
    variables: {
      ...options?.variables,
      offset,
      limit,
    },
    context: {
      uri: CONFIG.GRAPHQL_URL(options?.branch || currentBranch.name, date),
      ...options?.context,
    },
  });
};

export const useLazyQuery: typeof useApolloLazyQuery = (
  QUERY: any,
  options?: OperationVariables
) => {
  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);

  return useApolloLazyQuery(QUERY, {
    context: {
      uri: CONFIG.GRAPHQL_URL(currentBranch.name, date),
    },
    ...options,
  });
};

export const useMutation: typeof useApolloMutation<any, Record<string, any>, { uri: string }> = (
  QUERY,
  options
) => {
  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);

  return useApolloMutation(QUERY, {
    ...options,
    context: {
      uri: CONFIG.GRAPHQL_URL(currentBranch.name, date),
    },
  });
};

export default useQuery;
