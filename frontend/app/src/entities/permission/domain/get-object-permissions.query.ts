import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { getObjectPermissions } from "@/entities/permission/domain/get-object-permissions";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";

export const getObjectPermissionsQueryOptions = (kind: string) => {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["permissions", kind, currentBranchName, timeMachineDate],
    queryFn: () => {
      return getObjectPermissions({ kind, branchName: currentBranchName, atDate: timeMachineDate });
    },
  });
};

export const useGetObjectPermissions = (kind: string) => {
  return useQuery(getObjectPermissionsQueryOptions(kind));
};
