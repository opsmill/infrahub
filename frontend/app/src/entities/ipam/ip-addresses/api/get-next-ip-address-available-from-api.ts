import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

export const NEXT_IP_ADDRESS_QUERY = gql`
  query getNextIPAddressAvailable($parentPrefixId: String!) {
    InfrahubIPAddressGetNextAvailable(prefix_id: $parentPrefixId) {
      address
    }
  }
`;

export interface NextIPAddressAvailableData {
  InfrahubIPAddressGetNextAvailable: {
    address: string;
  };
}

export interface NextIPAddressAvailableVars {
  parentPrefixId: string;
}

export interface GetNextIPAddressAvailableFromApiParams
  extends NextIPAddressAvailableVars,
    ContextParams {}

export const getNextIpAddressAvailableFromApi = ({
  branchName,
  atDate,
  ...variables
}: GetNextIPAddressAvailableFromApiParams) => {
  return graphqlClient.query<NextIPAddressAvailableData, NextIPAddressAvailableVars>({
    query: NEXT_IP_ADDRESS_QUERY,
    variables,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
