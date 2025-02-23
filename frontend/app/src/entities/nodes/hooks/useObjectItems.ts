import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { getObjectItemsPaginated } from "@/entities/nodes/api/getObjectItems";
import {
  getObjectAttributes,
  getObjectRelationships,
} from "@/entities/nodes/object-items/getSchemaObjectColumns";
import { getPermission } from "@/entities/permission/utils";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { ModelSchema } from "@/entities/schema/types";
import { getTokens } from "@/entities/user-profile/api/getTokens";
import useQuery from "@/shared/api/graphql/useQuery";
import { Filter } from "@/shared/hooks/useFilters";
import { gql } from "@apollo/client";

const getQuery = (schema?: ModelSchema, filters?: Array<Filter>) => {
  if (!schema) return "query {ok}";

  if (schema.kind === ACCOUNT_TOKEN_OBJECT) {
    return getTokens;
  }

  const kindFilter = filters?.find((filter) => filter.name === "kind__value");
  const { schema: kindFilterSchema } = getSchema(kindFilter?.value);

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

  const isProfileSchema = schema.namespace === "Profile";

  return getObjectItemsPaginated({
    kind: kindFilterSchema?.kind || schema.kind,
    attributes,
    relationships,
    filters: filtersString,
    hasPermissions: !isProfileSchema,
  });
};

export const useObjectItems = (
  schema?: ModelSchema,
  filters?: Array<Filter>,
  kindFilter?: string
) => {
  const query = gql`
    ${getQuery(schema, filters)}
  `;

  const apolloQuery = useQuery(query, { notifyOnNetworkStatusChange: true, skip: !schema });

  const currentKind = kindFilter || schema?.kind;
  const hasPermission = !!(
    currentKind &&
    apolloQuery?.data &&
    apolloQuery?.data[currentKind]?.permissions
  );

  const permissionData = hasPermission ? apolloQuery.data[currentKind].permissions?.edges : null;

  const permission = getPermission(permissionData);

  return {
    ...apolloQuery,
    permission,
  };
};
