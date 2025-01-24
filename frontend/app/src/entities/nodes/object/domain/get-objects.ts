import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import { Filter } from "@/shared/hooks/useFilters";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const OBJECTS_PER_PAGE = 20;

////////////////////////////////////////////////////////////////////////////////////////////////////

export type GetObjects = (args: {
  schema: IModelSchema;
  offset?: number;
  branchName?: string;
  atDate?: Date | null;
  filters?: Array<Filter>;
}) => Promise<any>;

export const getObjects: GetObjects = async ({ schema, offset, branchName, atDate, filters }) => {
  const attributesVisible = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisibleInListView(schema.relationships ?? []);
  const schemaKind = schema.kind as string;

  const queryString = jsonToGraphQLQuery({
    query: {
      __name: `GetObjects${schemaKind}`,
      [schemaKind]: {
        __args: {
          limit: OBJECTS_PER_PAGE,
          offset,
          ...(filters
            ? filters.reduce(
                (acc, filter) => {
                  const [fieldName, fieldKey] = filter.name.split("__");

                  if (!fieldName || !fieldKey) return acc;

                  if (fieldKey === "value" || fieldKey === "values") {
                    acc[filter.name] = filter.value;
                    return acc;
                  }

                  if (fieldKey === "ids") {
                    acc[filter.name] = filter.value.map(({ id }: { id: string }) => id);
                  }

                  return acc;
                },
                { partial_match: true } as Record<string, string | number | boolean>
              )
            : {}),
        },
        edges: {
          node: {
            id: true,
            display_label: true,
            ...addAttributesToRequest(attributesVisible),
            ...addRelationshipsToRequest(relationshipsVisible),
          },
        },
      },
    },
  });

  const query = gql(queryString);
  const { data } = await graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });

  return data[schemaKind]?.edges?.map((edge: any) => edge.node) ?? [];
};
