import { queryOptions, useQuery } from "@tanstack/react-query";

import { proposedChangeValidatorsKeys } from "@/entities/diff/domain/diff.query-keys";
import { GetValidatorsParams, getValidators } from "@/entities/diff/domain/get-validators";

export const useGetValidatorsQuery = (params: GetValidatorsParams) => {
  return useQuery(
    queryOptions({
      queryKey: proposedChangeValidatorsKeys.allWithinProposedChange(params.proposedChangeId),
      queryFn: () => getValidators(params),
    })
  );
};
