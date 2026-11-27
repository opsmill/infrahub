import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const GET_IP_PREFIX_POOL = graphql(`
  query GET_IP_PREFIX_POOL($ids: [ID]) {
    CoreIPPrefixPool(ids: $ids) {
      edges {
        node {
          id
          hfid
          display_label
          __typename
          name {
            value
          }
          description {
            value
          }
          default_prefix_length {
            value
          }
          default_prefix_type {
            value
          }
          default_member_type {
            value
          }
          ip_namespace {
            node {
              id
              display_label
              ... on IpamNamespace {
                default {
                  value
                }
              }
            }
          }
        }
      }
    }
  }
`);

export type IpPrefixPoolNode = NonNullable<
  NonNullable<ResultOf<typeof GET_IP_PREFIX_POOL>["CoreIPPrefixPool"]["edges"][number]>["node"]
>;

export interface GetIpPrefixPoolFromApiParams extends ContextParams {
  poolId: string;
}

export function getIpPrefixPoolFromApi({
  poolId,
  branchName,
  atDate,
}: GetIpPrefixPoolFromApiParams) {
  return graphqlClient.query({
    query: GET_IP_PREFIX_POOL,
    variables: { ids: [poolId] },
    context: { branch: branchName, date: atDate },
  });
}
