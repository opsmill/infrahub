import { queryOptions, useQuery } from "@tanstack/react-query";

import { type GetValidatorsParams, getValidators } from "@/entities/diff/domain/get-validators";
import { proposedChangeValidatorsKeys } from "@/entities/diff/ui/queries/diff.query-keys";

export const useGetValidatorsQuery = (params: GetValidatorsParams) => {
  return useQuery(
    queryOptions({
      queryKey: proposedChangeValidatorsKeys.allWithinProposedChange(params.proposedChangeId),
      queryFn: () => getValidators(params),
    })
  );
};
