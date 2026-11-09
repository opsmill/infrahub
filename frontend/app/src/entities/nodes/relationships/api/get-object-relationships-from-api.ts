import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import {
  addAttributesToRequest,
  addFiltersToRequest,
  addRelationshipsToRequest,
} from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/domain/rules/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-list-view";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

type GenerateObjectRelationshipsQueryParams = PaginationParams & {
  parentKind: string;
  parentId: string;
  relationshipName: string;
  relationshipSchema: ModelSchema;
  filters?: Array<Filter>;
};

const generateObjectRelationshipsQuery = ({
  parentKind,
  parentId,
  relationshipName,
  relationshipSchema,
  limit = 0,
  offset = 0,
  filters,
}: GenerateObjectRelationshipsQueryParams) => {
  const { kind: relationshipKind, attributes = [], relationships = [] } = relationshipSchema;
  const attributesVisible = getAttributesVisibleInListView(attributes);
  const relationshipsVisible = getRelationshipsVisibleInListView(relationships);

  const request = {
    query: {
      __name: `Get${parentKind}Relationships${relationshipKind}`,
      [parentKind]: {
        __args: {
          ids: [parentId],
        },
        edges: {
          node: {
            [relationshipName]: {
              __args: {
                limit,
                offset,
                ...(filters ? addFiltersToRequest(filters) : {}),
              },
              edges: {
                node: {
                  __on: {
                    __typeName: relationshipKind,
                    __args: {
                      limit,
                      offset,
                    },
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
  ...params
}: GetObjectRelationshipsFromApiParams) => {
  const query = graphql(generateObjectRelationshipsQuery(params));

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
