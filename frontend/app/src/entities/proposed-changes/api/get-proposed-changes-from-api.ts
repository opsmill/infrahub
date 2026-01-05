import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import {
  addAttributesToRequest,
  addFiltersToRequest,
  addRelationshipsToRequest,
} from "@/shared/api/graphql/utils";
import type { PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const OBJECTS_PER_PAGE = 40;

////////////////////////////////////////////////////////////////////////////////////////////////////

export interface ProposedChangesFromApiParams extends PaginationParams {
  schema: ModelSchema;
  filters?: Array<Filter>;
  getAttributesVisible?: (attributes: AttributeSchema[]) => AttributeSchema[];
  getRelationshipsVisible?: (relationships: RelationshipSchema[]) => RelationshipSchema[];
}

export const getProposedChangesFromApi = async ({
  schema,
  limit = OBJECTS_PER_PAGE,
  offset,
  filters,
  getAttributesVisible = getAttributesVisibleInListView,
  getRelationshipsVisible = getRelationshipsVisibleInListView,
}: ProposedChangesFromApiParams) => {
  const attributesVisible = getAttributesVisible(schema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisible(schema.relationships ?? []);

  const schemaKindToQuery = schema.kind as string;

  const queryString = jsonToGraphQLQuery({
    query: {
      __name: `Get${PROPOSED_CHANGE_OBJECT}`,
      [schemaKindToQuery]: {
        __args: {
          limit,
          offset,
          ...(filters ? addFiltersToRequest(filters) : {}),
        },
        edges: {
          node: {
            id: true,
            display_label: true,
            hfid: true,
            _updated_at: true,
            total_comments: {
              value: true,
            },
            validations: {
              count: true,
            },
            ...addAttributesToRequest(attributesVisible),
            ...addRelationshipsToRequest(relationshipsVisible),
          },
        },
      },
    },
  });

  const query = gql(queryString);
  return graphqlClient.query({
    query,
  });
};
