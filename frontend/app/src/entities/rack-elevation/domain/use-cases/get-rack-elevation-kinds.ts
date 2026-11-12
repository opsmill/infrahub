import {
  type GetRackElevationKindsFromApiParams,
  getRackElevationKindsFromApi,
} from "@/entities/rack-elevation/api/get-rack-elevation-kinds-from-api";
import type { RackElevationKind } from "@/entities/rack-elevation/domain/model/rack-elevation";

export type GetRackElevationKindsParams = GetRackElevationKindsFromApiParams;
export type GetRackElevationKindsResult = RackElevationKind[];

export const getRackElevationKinds = async (
  params: GetRackElevationKindsParams
): Promise<GetRackElevationKindsResult> => {
  const { data, errors } = await getRackElevationKindsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.RackElevationKinds;
};
