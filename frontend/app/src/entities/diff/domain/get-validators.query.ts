import { queryOptions, useQuery } from "@tanstack/react-query";

import { GetValidatorsFromApiParams } from "../api/get-validators-from-api";
import { proposedChangeValidatorsKeys } from "./diff.query-keys";
import { getValidators } from "./get-validators";

export const useGetValidatorsQuery = (params: GetValidatorsFromApiParams) => {
  return useQuery(
    queryOptions({
      queryKey: proposedChangeValidatorsKeys.allWithinProposedChange(params.proposedChangeId),
      queryFn: () => getValidators(params),
    })
  );
};
