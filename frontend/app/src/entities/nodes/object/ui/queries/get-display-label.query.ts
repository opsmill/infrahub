import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { findSelectedBranch } from "@/entities/branches/domain/rules/find-selected-branch";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import { getNodeLabelFromApi } from "@/entities/nodes/object/api/get-display-label-from-api";

type NodeLabelProps = {
  objectId?: string | null;
  kind: string;
  enabled?: boolean;
  branch?: string | null;
  atDate?: Date | null;
};

export function getNodeLabelQueryOptions({
  objectId,
  kind,
  enabled,
  branchName,
  atDate,
}: NodeLabelProps & ContextParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "display-label", objectId, kind],
    queryFn: () => {
      return getNodeLabelFromApi({
        objectId,
        kind,
        branchName,
        atDate,
      });
    },
    enabled,
  });
}

export const useNodeLabel = ({ objectId, kind, enabled, branch, atDate }: NodeLabelProps) => {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const { data: branches, isPending: isBranchListPending } = useGetBranches();

  // A historical record can name a branch deleted since; querying it would only return a 404.
  const isBranchMissing = !!branch && !!branches && !findSelectedBranch(branches, branch);
  const isBranchChecked = !branch || !isBranchListPending;

  const { data, isPending, error } = useQuery(
    getNodeLabelQueryOptions({
      objectId,
      kind,
      enabled: (enabled ?? true) && isBranchChecked && !isBranchMissing,
      branchName: branch ?? currentBranch.name,
      atDate: atDate ?? timeMachineDate,
    })
  );

  if (isBranchMissing) {
    // The query never runs for a missing branch, so it is reported as settled instead of pending forever.
    return {
      data: {},
      isPending: false,
      error: new Error(`Branch ${branch} no longer exists`),
    };
  }

  return {
    data: data?.data?.[kind]?.edges?.[0]?.node ?? {},
    isPending,
    error,
  };
};
