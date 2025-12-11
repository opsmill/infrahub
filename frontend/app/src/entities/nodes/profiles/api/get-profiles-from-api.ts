import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams } from "@/shared/api/types";

import type { ProfileSchema } from "@/entities/schema/types";

function buildGetProfilesQuery(profileSchemas: ProfileSchema[]): string {
  return jsonToGraphQLQuery({
    query: {
      __name: "GetProfiles",
      ...profileSchemas.reduce((acc, profileSchema) => {
        return {
          ...acc,
          [profileSchema.kind!]: {
            edges: {
              node: {
                id: true,
                display_label: true,
                hfid: true,
                ...addAttributesToRequest(profileSchema.attributes ?? [], { withMetadata: true }),
                ...addRelationshipsToRequest(profileSchema.relationships ?? [], {
                  withMetadata: true,
                }),
              },
            },
          },
        };
      }, {}),
    },
  });
}

export interface GetProfilesFromApiParams extends ContextParams {
  profileSchemas: ProfileSchema[];
}

export function getProfilesFromApi({
  profileSchemas,
  branchName,
  atDate,
}: GetProfilesFromApiParams) {
  const getProfilesQueryString = buildGetProfilesQuery(profileSchemas);

  return graphqlClient.query({
    query: gql(getProfilesQueryString),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
