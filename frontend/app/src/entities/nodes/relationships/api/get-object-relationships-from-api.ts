import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import {
  addAttributesToRequest,
  addFiltersToRequest,
  addRelationshipsToRequest,
} from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import type { ModelSchema } from "@/entities/schema/types";

type GenerateObjectRelationshipsQueryParams = PaginationParams & {
  parentKind: string;
  parentId: string;
  relationshipName: string;
  relationshipSchema: ModelSchema;
  filters?: Array<Filter>;
};

const generateObjectRelationshipsQuery = ({
  parentKind,
  relationshipName,
  relationshipSchema,
  filters,
}: Omit<GenerateObjectRelationshipsQueryParams, "limit" | "offset" | "parentId">) => {
  const { kind: relationshipKind, attributes = [], relationships = [] } = relationshipSchema;
  const attributesVisible = getAttributesVisibleInListView(attributes);
  const relationshipsVisible = getRelationshipsVisibleInListView(relationships);

  const request = {
    query: {
      __name: `Get${parentKind}Relationships${relationshipKind}`,
      __variables: {
        parentIds: "[ID]",
        limit: "Int",
        offset: "Int",
      },
      [parentKind]: {
        __args: {
          ids: new VariableType("parentIds"),
        },
        edges: {
          node: {
            [relationshipName]: {
              __args: {
                limit: new VariableType("limit"),
                offset: new VariableType("offset"),
                ...(filters ? addFiltersToRequest(filters) : {}),
              },
              edges: {
                node: {
                  __on: {
                    __typeName: relationshipKind,
                    id: true,
                    hfid: true,
                    display_label: true,
                    ...addAttributesToRequest(attributesVisible),
                    ...addRelationshipsToRequest(relationshipsVisible),
                  },
                },
              },
            },
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};

export type GetObjectRelationshipsFromApiParams = ContextParams &
  GenerateObjectRelationshipsQueryParams;

export const getObjectRelationshipsFromApi = ({
  branchName,
  atDate,
  limit,
  offset,
  parentId,
  ...params
}: GetObjectRelationshipsFromApiParams) => {
  const query = gql(generateObjectRelationshipsQuery(params));

  return graphqlClient.query({
    query,
    variables: { parentIds: [parentId], limit, offset },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
