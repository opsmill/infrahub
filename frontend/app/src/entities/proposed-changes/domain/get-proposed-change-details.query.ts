import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useConfig } from "@/entities/config/get-config.query";
import { PROPOSED_CHANGE_THREAD } from "@/entities/proposed-changes/constants";
import { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { ProposedChangeDetailsFromApiParams } from "../api/get-proposed-change-details-from-api";
import { getProposedChangeDetails } from "./get-proposed-change-details";
import { useUpdateProposedChangeStateCheck } from "./update-proposed-change-check-state.mutation";

type GetProposedChangeDetailsQueryOptionsParams = Omit<
  ProposedChangeDetailsFromApiParams,
  keyof PaginationParams
>;

export function getProposedChangeDetailsQueryOptions({
  id,
  nodeId,
  state,
  branchName,
  atDate,
}: GetProposedChangeDetailsQueryOptionsParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "objects", PROPOSED_CHANGE_THREAD, id, nodeId, state],
    queryFn: () => {
      return getProposedChangeDetails({
        branchName,
        atDate,
        id,
        nodeId,
        state,
      });
    },
  });
}

export function useGetProposedChangeDetails(
  params: Omit<GetProposedChangeDetailsQueryOptionsParams, keyof ContextParams>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const { data: config } = useConfig();

  const mutation = useUpdateProposedChangeStateCheck({});

  return useQuery({
    ...getProposedChangeDetailsQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    }),
    queryFn: async (context) => {
      if (config.policy?.revoke_proposed_change_approvals) {
        await mutation.mutateAsync({ proposedChangeId: params.id });
      }

      const originalFn = getProposedChangeDetailsQueryOptions({
        ...params,
        branchName: currentBranch.name,
        atDate: timeMachineDate,
      }).queryFn;

      if (!originalFn) {
        throw new Error("Query function is undefined");
      }

      return originalFn(context);
    },
  });
}
