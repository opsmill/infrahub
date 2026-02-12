import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectPermissions } from "@/entities/permission/domain/get-object-permissions";
import type { GetPermissionOptions } from "@/entities/permission/utils";
import type { ModelSchema } from "@/entities/schema/types";

export interface GetObjectPermissionsParams extends ContextParams, GetPermissionOptions {
  userId?: string;
}

export const getObjectPermissionsQueryOptions = ({
  userId,
  branchName,
  atDate,
  branch,
  schema,
}: GetObjectPermissionsParams) => {
  const kind = schema.kind!;

  return queryOptions({
    queryKey: [branchName, atDate, "permissions", kind, userId, branch?.status],
    queryFn: () => {
      return getObjectPermissions({ branchName, atDate, branch, schema });
    },
  });
};

export const useGetObjectPermissions = (schema: ModelSchema) => {
  const auth = useAuth();
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getObjectPermissionsQueryOptions({
      userId: auth.user?.id,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      branch: currentBranch,
      schema,
    })
  );
};
