import { queryOptions, useQuery } from "@tanstack/react-query";

import { GetCheckDetailsFromApiParams } from "@/entities/diff/api/get-check-details-from-api";
import { getCheckQueryKeys } from "@/entities/diff/domain/diff.query-keys";
import { getCheckDetails } from "@/entities/diff/domain/get-check-details";

export const useGetCheckDetailsQuery = (params: GetCheckDetailsFromApiParams) => {
  return useQuery(
    queryOptions({
      queryKey: getCheckQueryKeys.details(params.checkId),
      queryFn: () => getCheckDetails(params),
    })
  );
};
