import { queryOptions, useQuery } from "@tanstack/react-query";

import { GetValidatorsFromApiParams } from "../api/get-validators-from-api";
import { getValidators } from "./get-validators";

export const useGetValidatorsQuery = (params: GetValidatorsFromApiParams) => {
  return useQuery(
    queryOptions({
      queryKey: ["proposed-change-validators", params.proposedChangeId],
      queryFn: () => getValidators(params),
    })
  );
};
