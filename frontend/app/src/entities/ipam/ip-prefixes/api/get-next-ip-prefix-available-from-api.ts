import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const NEXT_IP_PREFIX_QUERY = graphql(`
  query getNextIPPrefixAvailable($parentPrefixId: String!) {
    InfrahubIPPrefixGetNextAvailable(prefix_id: $parentPrefixId) {
      prefix
    }
  }
`);

type QueryVariables = VariablesOf<typeof NEXT_IP_PREFIX_QUERY>;

export interface GetNextIPPrefixGetNextAvailableFromApiParams
  extends QueryVariables,
    ContextParams {}

export const getNextIpPrefixAvailableFromApi = ({
  parentPrefixId,
  branchName,
  atDate,
}: GetNextIPPrefixGetNextAvailableFromApiParams) => {
  return graphqlClient.query({
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
