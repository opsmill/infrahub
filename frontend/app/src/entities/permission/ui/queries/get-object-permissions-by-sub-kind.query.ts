import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectPermissionsBySubKind } from "@/entities/permission/domain/get-object-permissions-by-sub-kind";
import type { GetPermissionOptions } from "@/entities/permission/utils";

export interface GetObjectPermissionsBySubKindParams extends ContextParams, GetPermissionOptions {
  kind: string;
  userId?: string;
}

export function getObjectPermissionsBySubKindQueryOptions({
  userId,
  branchName,
  atDate,
  branch,
  kind,
}: GetObjectPermissionsBySubKindParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "permissions-by-sub-kind", kind, userId, branch?.status],
    queryFn: () => getObjectPermissionsBySubKind({ branchName, atDate, branch, kind }),
  });
}

export function useGetObjectPermissionsBySubKind(kind: string) {
  const auth = useAuth();
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getObjectPermissionsBySubKindQueryOptions({
      userId: auth.user?.id,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      branch: currentBranch,
      kind,
    })
  );
}
