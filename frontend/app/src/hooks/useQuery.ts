import { CONFIG } from "@/config/config";
import { WSClient } from "@/graphql/websocket";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import {
  OperationVariables,
  useLazyQuery as useApolloLazyQuery,
  useMutation as useApolloMutation,
  useQuery as useApolloQuery,
  useSubscription as useApolloSubscription,
} from "@apollo/client";
import { useAtomValue } from "jotai";
import usePagination from "./usePagination";

interface Options extends OperationVariables {
  branch?: string;
  context?: Record<string, string | boolean | ((message: string) => void)>;
}

const useQuery: typeof useApolloQuery = (QUERY, options?: Options) => {
  const branch = useAtomValue(currentBranchAtom);
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
      uri: CONFIG.GRAPHQL_URL(options?.branch || branch?.name, date),
      ...options?.context,
    },
  });
};

export const useLazyQuery: typeof useApolloLazyQuery = (
  QUERY: any,
  options?: OperationVariables
) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  return useApolloLazyQuery(QUERY, {
    context: {
      uri: CONFIG.GRAPHQL_URL(branch?.name, date),
    },
    ...options,
  });
};

export const useMutation: typeof useApolloMutation<any, Record<string, any>, { uri: string }> = (
  QUERY,
  options
) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  return useApolloMutation(QUERY, {
    ...options,
    context: {
      uri: CONFIG.GRAPHQL_URL(branch?.name, date),
    },
  });
};

const client = new WSClient();

export const useSubscription = (QUERY: any, options?: OperationVariables) => {
  const branch = useAtomValue(currentBranchAtom);

  const wsClient = client.getClient(branch?.name);

  return useApolloSubscription(QUERY, {
    client: wsClient,
    ...options,
  });
};

export default useQuery;
