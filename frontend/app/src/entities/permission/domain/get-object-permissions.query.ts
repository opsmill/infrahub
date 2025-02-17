import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { useAuth } from "@/entities/authentication/ui/useAuth";
import { currentBranchAtom } from "@/entities/branches/stores";
import { getObjectPermissions } from "@/entities/permission/domain/get-object-permissions";
import { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

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
  const currentBranch = useAtomValue(currentBranchAtom);
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getObjectPermissionsQueryOptions({
      kind,
      userId: auth.user?.id,
      branchName: currentBranch?.name ?? DEFAULT_BRANCH_NAME,
      atDate: timeMachineDate,
    })
  );
};
