import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list";
import { NodeObject } from "@/entities/nodes/types";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import { ContextParams, PaginationParams } from "@/shared/api/types";
import { Filter } from "@/shared/hooks/useFilters";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const OBJECTS_PER_PAGE = 40;

////////////////////////////////////////////////////////////////////////////////////////////////////

export type GetObjects = (
  args: ContextParams &
    PaginationParams & {
      schema: IModelSchema;
      filters?: Array<Filter>;
    }
) => Promise<Array<NodeObject>>;

export const getObjects: GetObjects = async ({
  schema,
  limit = OBJECTS_PER_PAGE,
  offset,
  branchName,
  atDate,
  filters,
}) => {
  const attributesVisible = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisibleInListView(schema.relationships ?? []);

  const schemaKind = schema.kind as string;
  const kindFilter = filters?.find((filter) => filter.name === "kind__value");
  const schemaKindToQuery: string = kindFilter?.value ?? schemaKind;

  const queryString = jsonToGraphQLQuery({
    query: {
      __name: `GetObjects${schemaKind}`,
      [schemaKindToQuery]: {
        __args: {
          limit,
          offset,
          ...(filters
            ? filters.reduce(
                (acc, filter) => {
                  if (filter.name === "kind__value") return acc;

                  const [fieldName, fieldKey] = filter.name.split("__");

                  if (!fieldName || !fieldKey) return acc;

                  if (fieldKey === "value" || fieldKey === "values" || fieldKey === "isnull") {
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
            hfid: true,
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

  return data[schemaKindToQuery]?.edges?.map((edge: any) => edge.node) ?? [];
};
