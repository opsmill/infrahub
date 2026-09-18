import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

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
  // The pagination bounds used to be inlined into the document with these defaults;
  // keep defaulting them here so an omitted bound still reaches the API as 0, not null.
  limit = 0,
  offset = 0,
  parentId,
  ...params
}: GetObjectRelationshipsFromApiParams) => {
  const query = graphql(generateObjectRelationshipsQuery(params));

  return graphqlClient.query({
    query,
    variables: { parentIds: [parentId], limit, offset },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
