import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

export const NEXT_IP_PREFIX_QUERY = gql`
  query getNextIPPrefixAvailable($parentPrefixId: String!) {
    InfrahubIPPrefixGetNextAvailable(prefix_id: $parentPrefixId) {
      prefix
    }
  }
`;

export interface NextIPPrefixAvailableData {
  InfrahubIPPrefixGetNextAvailable: {
    prefix: string;
  };
}

export interface NextIPPrefixAvailableQueryVars {
  parentPrefixId: string;
}

export interface GetNextIPPrefixGetNextAvailableFromApiParams
  extends NextIPPrefixAvailableQueryVars,
    ContextParams {}

export const getNextIpPrefixAvailableFromApi = ({
  parentPrefixId,
  branchName,
  atDate,
}: GetNextIPPrefixGetNextAvailableFromApiParams) => {
  return graphqlClient.query<NextIPPrefixAvailableData, NextIPPrefixAvailableQueryVars>({
    query: NEXT_IP_PREFIX_QUERY,
    variables: {
      parentPrefixId,
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
