import useQuery from "@/hooks/useQuery";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { gql } from "@apollo/client";
import { getObjectItemsPaginated } from "@/graphql/queries/objects/getObjectItems";
import { getObjectAttributes, getObjectRelationships } from "@/utils/getSchemaObjectColumns";
import usePagination from "@/hooks/usePagination";
import useFilters from "@/hooks/useFilters";

export const useObjectItems = (schema?: IModelSchema, filtersFromProps: Array<string> = []) => {
  const [filters] = useFilters();
  const [pagination] = usePagination();

  // All the filter values are being sent out as strings inside quotes.
  // This will not work if the type of filter value is not string.
  const filtersString = [
    // Add object filters
    ...filters
      .filter((filter) => filter.name !== "kind__value")
      .map((row) => {
        if (typeof row.value === "string") {
          return `${row.name}: "${row.value}"`;
        }

        if (Array.isArray(row.value)) {
          return `${row.name}: ${JSON.stringify(row.value.map((v) => v.id ?? v))}`;
        }

        return `${row.name}: ${row.value}`;
      }),
    // Add pagination filters
    ...[
      { name: "offset", value: pagination.offset },
      { name: "limit", value: pagination.limit },
    ].map((row: any) => `${row.name}: ${row.value}`),
    ...filtersFromProps,
  ].join(",");

  const attributes = getObjectAttributes({ schema, forListView: true });
  const relationships = getObjectRelationships({ schema, forListView: true });

  const query = gql(
    schema
      ? getObjectItemsPaginated({
          kind: schema.kind,
          attributes,
          relationships,
          filters: filtersString,
        })
      : "query {ok}"
  );
  return useQuery(query, { notifyOnNetworkStatusChange: true, skip: !schema });
};
