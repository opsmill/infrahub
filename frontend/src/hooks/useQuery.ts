import {
  OperationVariables,
  useLazyQuery as useApolloLazyQuery,
  useQuery as useApolloQuery,
  useSubscription as useApolloSubscription,
} from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { CONFIG } from "../config/config";
import { WSClient } from "../graphql/websocket";
import { currentBranchAtom } from "../state/atoms/branches.atom";
import { datetimeAtom } from "../state/atoms/time.atom";
import usePagination from "./usePagination";

const useQuery = (QUERY: any, options?: OperationVariables) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [{ offset, limit }] = usePagination();
  console.log("limit: ", limit);
  console.log("offset: ", offset);

  return useApolloQuery(QUERY, {
    ...options,
    variables: {
      ...options?.variables,
      offset,
      limit,
    },
    context: {
      uri: CONFIG.GRAPHQL_URL(branch?.name, date),
    },
  });
};

export const useLazyQuery = (QUERY: any, options?: OperationVariables) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  return useApolloLazyQuery(QUERY, {
    context: {
      uri: CONFIG.GRAPHQL_URL(branch?.name, date),
    },
    ...options,
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
