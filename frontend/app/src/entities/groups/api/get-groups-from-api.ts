import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";
import Handlebars from "@/shared/libs/handlebars";

const getGroupsQuery = Handlebars.compile(`
query GET_GROUPS {
  {{objectKind}}(ids:["{{objectId}}"]) {
    edges {
      node {
        member_of_groups {
          count
          edges {
            node {
              id
              display_label
              description {
                value
              }
              group_type {
                value
              }
              members {
                count
              }
            }
          }
        }
      }
    }
    permissions {
      edges {
        node {
          kind
          view
          create
          update
          delete
        }
      }
    }
  }
}
`);

export interface GetGroupsFromApiParams extends ContextParams {
  objectKind: string;
  objectId: string;
}

export function getGroupsFromApi({
  objectKind,
  objectId,
  branchName,
  atDate,
}: GetGroupsFromApiParams) {
  const query = gql(getGroupsQuery({ objectKind, objectId }));

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
