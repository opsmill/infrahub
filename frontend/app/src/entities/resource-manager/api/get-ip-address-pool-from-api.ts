import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const GET_IP_ADDRESS_POOL = graphql(`
  query GET_IP_ADDRESS_POOL($ids: [ID]) {
    CoreIPAddressPool(ids: $ids) {
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
          default_address_type {
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

export type IpAddressPoolNode = NonNullable<
  NonNullable<ResultOf<typeof GET_IP_ADDRESS_POOL>["CoreIPAddressPool"]["edges"][number]>["node"]
>;

export interface GetIpAddressPoolFromApiParams extends ContextParams {
  poolId: string;
}

export function getIpAddressPoolFromApi({
  poolId,
  branchName,
  atDate,
}: GetIpAddressPoolFromApiParams) {
  return graphqlClient.query({
    query: GET_IP_ADDRESS_POOL,
    variables: { ids: [poolId] },
    context: { branch: branchName, date: atDate },
  });
}
