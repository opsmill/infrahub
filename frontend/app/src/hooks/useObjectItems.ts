import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { getTokens } from "@/graphql/queries/accounts/getTokens";
import { getObjectItemsPaginated } from "@/graphql/queries/objects/getObjectItems";
import { Filter } from "@/hooks/useFilters";
import useQuery from "@/hooks/useQuery";
import { IModelSchema, genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { getObjectAttributes, getObjectRelationships } from "@/utils/getSchemaObjectColumns";
import { getPermission } from "@/utils/permissions";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";

const getQuery = (schema?: IModelSchema, filters?: Array<Filter>) => {
  if (!schema) return "query {ok}";

  if (schema.kind === ACCOUNT_TOKEN_OBJECT) {
    return getTokens;
  }

  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const kindFilter = filters?.find((filter) => filter.name == "kind__value");

  const kindFilterSchema = [...nodes, ...generics, ...profiles].find(
    ({ kind }) => kind === kindFilter?.value
  );

  // All the filter values are being sent out as strings inside quotes.
  // This will not work if the type of filter value is not string.
  const filtersString = filters
    ? [
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
      ].join(",")
    : "";

  const attributes = getObjectAttributes({ schema, forListView: true });

  const relationships = getObjectRelationships({ schema, forListView: true });

  return getObjectItemsPaginated({
    kind: kindFilterSchema?.kind || schema.kind,
    attributes,
    relationships,
    filters: filtersString,
  });
};

export const useObjectItems = (
  schema?: IModelSchema,
  filters?: Array<Filter>,
  kindFilter?: string
) => {
  const query = gql`
    ${getQuery(schema, filters)}
  `;

  const apolloQuery = useQuery(query, { notifyOnNetworkStatusChange: true, skip: !schema });

  const permission = getPermission(
    schema?.kind &&
      apolloQuery?.data &&
      apolloQuery?.data[kindFilter || schema?.kind]?.permissions?.edges[0]?.node
  );

  return {
    ...apolloQuery,
    permission,
  };
};
