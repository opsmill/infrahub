import { queryOptions, useQuery } from "@tanstack/react-query";

import { getCheckQueryKeys } from "@/entities/diff/ui/queries/diff.query-keys";
import {
  type GetCheckDetailsParams,
  getCheckDetails,
} from "@/entities/diff/domain/get-check-details";

export const useGetCheckDetails = (params: GetCheckDetailsParams) => {
  return useQuery(
    queryOptions({
      queryKey: getCheckQueryKeys.details(params.checkId),
      queryFn: () => getCheckDetails(params),
    })
  );
};
