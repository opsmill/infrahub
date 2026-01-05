import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectPermissions } from "@/entities/permission/domain/get-object-permissions";

export type GetObjectPermissionsParams = ContextParams & {
  kind: string;
  userId?: string;
};

export const getObjectPermissionsQueryOptions = ({
  kind,
  userId,
  branchName,
  atDate,
}: GetObjectPermissionsParams) => {
  return queryOptions({
    queryKey: [branchName, atDate, "permissions", kind, userId],
    queryFn: () => {
      return getObjectPermissions({ kind, branchName, atDate });
    },
  });
};

export const useGetObjectPermissions = (kind: string) => {
  const auth = useAuth();
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getObjectPermissionsQueryOptions({
      kind,
      userId: auth.user?.id,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
};
