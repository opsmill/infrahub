import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list";
import { ModelSchema } from "@/entities/schema/types";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import {
  addAttributesToRequest,
  addFiltersToRequest,
  addRelationshipsToRequest,
} from "@/shared/api/graphql/utils";
import { Filter } from "@/shared/hooks/useFilters";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

type GenerateObjectRelationshipsQueryParams = {
  parentKind: string;
  parentId: string;
  relationshipName: string;
  relationshipSchema: ModelSchema;
  limit?: number;
  offset?: number;
  filters?: Array<Filter>;
};

const generateObjectRelationshipsQuery = ({
  parentKind,
  parentId,
  relationshipName,
  relationshipSchema,
  limit,
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

export type GetObjectRelationshipsFromApiParams = GenerateObjectRelationshipsQueryParams & {
  branchName: string;
  atDate: Date | null;
};

export const getObjectRelationshipsFromApi = ({
  branchName,
  atDate,
  ...params
}: GetObjectRelationshipsFromApiParams) => {
  const query = gql(generateObjectRelationshipsQuery(params));

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
