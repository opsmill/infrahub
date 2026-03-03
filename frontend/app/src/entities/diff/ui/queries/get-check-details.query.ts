import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  type GetCheckDetailsParams,
  getCheckDetails,
} from "@/entities/diff/domain/get-check-details";
import { getCheckQueryKeys } from "@/entities/diff/ui/queries/diff.query-keys";

export const useGetCheckDetails = (params: GetCheckDetailsParams) => {
  return useQuery(
    queryOptions({
      queryKey: getCheckQueryKeys.details(params.checkId),
      queryFn: () => getCheckDetails(params),
    })
  );
};
