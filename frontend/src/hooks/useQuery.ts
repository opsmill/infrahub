import {
  OperationVariables,
  useQuery as useApolloQuery,
  useLazyQuery as useApolloLazyQuery,
  useSubscription as useApolloSubscription,
} from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { currentBranchAtom } from "../state/atoms/branches.atom";
import { datetimeAtom } from "../state/atoms/time.atom";
import { CONFIG } from "../config/config";
import { WSClient } from "../graphql/websocket";

const useQuery = (QUERY: any, options?: OperationVariables) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  return useApolloQuery(QUERY, {
    ...options,
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
