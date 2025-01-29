import { useAuth } from "@/entities/authentication/ui/useAuth";
import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { getObjectPermissions } from "@/entities/permission/domain/get-object-permissions";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";

export interface GetObjectPermissionsParams {
  kind: string;
  userId?: string;
}

export const getObjectPermissionsQueryOptions = ({ kind, userId }: GetObjectPermissionsParams) => {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["permissions", userId, kind, currentBranchName, timeMachineDate],
    queryFn: () => {
      return getObjectPermissions({ kind, branchName: currentBranchName, atDate: timeMachineDate });
    },
  });
};

export const useGetObjectPermissions = (kind: string) => {
  const auth = useAuth();
  return useQuery(getObjectPermissionsQueryOptions({ kind, userId: auth.user?.id }));
};
