import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  type GetValidatorDetailsParams,
  getValidatorDetails,
} from "@/entities/diff/domain/get-validator-details";
import { validatorDetailsKeys } from "@/entities/diff/ui/queries/diff.query-keys";

export function getValidatorDetailsQueryOptions(params: GetValidatorDetailsParams) {
  return queryOptions({
    queryKey: validatorDetailsKeys.detail(
      params.ids?.[0] ?? "",
      params.checksOffset ?? undefined,
      params.checksLimit ?? undefined
    ),
    queryFn: () => getValidatorDetails(params),
  });
}

export function useGetValidatorDetails(params: GetValidatorDetailsParams) {
  return useQuery(getValidatorDetailsQueryOptions(params));
}
