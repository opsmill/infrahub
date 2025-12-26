import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

const NEXT_IP_ADDRESS_QUERY = graphql(`
  query getNextIPAddressAvailable($parentPrefixId: String!) {
    InfrahubIPAddressGetNextAvailable(prefix_id: $parentPrefixId) {
      address
    }
  }
`);

type QueryVariables = VariablesOf<typeof NEXT_IP_ADDRESS_QUERY>;

export interface GetNextIPAddressAvailableFromApiParams extends QueryVariables, ContextParams {}

export const getNextIpAddressAvailableFromApi = ({
  branchName,
  atDate,
  ...variables
}: GetNextIPAddressAvailableFromApiParams) => {
  return graphqlClient.query({
    query: NEXT_IP_ADDRESS_QUERY,
    variables,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
