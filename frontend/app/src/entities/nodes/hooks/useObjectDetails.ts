import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";

import useQuery from "@/shared/api/graphql/useQuery";
import { PROFILE_KIND, TASK_OBJECT } from "@/shared/config/constants";

import { getObjectDetailsPaginated } from "@/entities/nodes/api/getObjectDetails";
import { getRelationshipsVisibleInTab } from "@/entities/nodes/object/utils/get-relationships-visible-in-tab";
import { getSchemaObjectColumns } from "@/entities/nodes/object-items/getSchemaObjectColumns";
import { getPermission } from "@/entities/permission/utils";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

export const useObjectDetails = (schema: ModelSchema, objectId: string) => {
  const generics = useAtomValue(genericSchemasAtom);
  const profileGenericSchema = generics.find((s) => s.kind === PROFILE_KIND);

  const relationshipsTabs = getRelationshipsVisibleInTab(schema.relationships ?? []);
  const columns = getSchemaObjectColumns({ schema });

  const isProfileSchema = schema?.namespace === "Profile";
  const query = gql(
    schema
      ? getObjectDetailsPaginated({
          kind: schema?.kind,
          taskKind: TASK_OBJECT,
          columns,
          relationshipsTabs,
          objectId,
          // Do not query profiles on profiles nodes
          queryProfiles:
            !profileGenericSchema?.used_by?.includes(schema?.kind!) &&
            schema?.kind !== PROFILE_KIND &&
            !isGenericSchema(schema) &&
            schema?.generate_profile,
          hasPermissions: !isProfileSchema,
        })
      : // Empty query to make the gql parsing work
        // TODO: Find another solution for queries while loading schema
        "query { ok }"
  );

  const apolloQuery = useQuery(query, {
    skip: !schema,
    notifyOnNetworkStatusChange: true,
  });

  const permissionData =
    schema?.kind && apolloQuery?.data?.[schema.kind]?.permissions?.edges
      ? apolloQuery.data[schema.kind].permissions.edges
      : null;

  const permission = getPermission(permissionData);

  return {
    ...apolloQuery,
    permission,
  };
};
