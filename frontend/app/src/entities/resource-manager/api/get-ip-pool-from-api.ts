import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const GET_IP_POOL = graphql(`
  query GET_IP_POOL($ids: [ID]) {
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

type IpPoolResult = ResultOf<typeof GET_IP_POOL>;

export type IpPrefixPoolNode = NonNullable<
  NonNullable<IpPoolResult["CoreIPPrefixPool"]["edges"][number]>["node"]
>;
export type IpAddressPoolNode = NonNullable<
  NonNullable<IpPoolResult["CoreIPAddressPool"]["edges"][number]>["node"]
>;

export interface GetIpPoolFromApiParams extends ContextParams {
  poolId: string;
}

export function getIpPoolFromApi({ poolId, branchName, atDate }: GetIpPoolFromApiParams) {
  return graphqlClient.query({
    query: GET_IP_POOL,
    variables: { ids: [poolId] },
    context: { branch: branchName, date: atDate },
  });
}
