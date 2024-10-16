import { PROFILE_KIND, TASK_OBJECT } from "@/config/constants";
import { getObjectDetailsPaginated } from "@/graphql/queries/objects/getObjectDetails";
import useQuery from "@/hooks/useQuery";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { IModelSchema, genericsState } from "@/state/atoms/schema.atom";
import { isGeneric } from "@/utils/common";
import { getSchemaObjectColumns, getTabs } from "@/utils/getSchemaObjectColumns";
import { PERMISSION_ALLOW, getPermission } from "@/utils/permissions";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";

export const useObjectDetails = (schema: IModelSchema, objectId: string) => {
  const currentBranch = useAtomValue(currentBranchAtom);
  const generics = useAtomValue(genericsState);
  const profileGenericSchema = generics.find((s) => s.kind === PROFILE_KIND);

  const relationshipsTabs = getTabs(schema);
  const columns = getSchemaObjectColumns({ schema });

  const isProfileSchema = schema.namespace === "Profile";
  const query = gql(
    schema
      ? getObjectDetailsPaginated({
          kind: schema?.kind,
          taskKind: TASK_OBJECT,
          columns,
          relationshipsTabs,
          objectid: objectId,
          // Do not query profiles on profiles objects
          queryProfiles:
            !profileGenericSchema?.used_by?.includes(schema?.kind!) &&
            schema?.kind !== PROFILE_KIND &&
            !isGeneric(schema) &&
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

  const permission = permissionData
    ? getPermission(permissionData, currentBranch)
    : PERMISSION_ALLOW;

  return {
    ...apolloQuery,
    permission,
  };
};
