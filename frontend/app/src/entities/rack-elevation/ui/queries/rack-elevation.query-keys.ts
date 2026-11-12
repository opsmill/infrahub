export interface RackElevationKindsKeysParams {
  branchName: string;
  atDate?: Date | null;
}

export interface RackElevationKeysParams {
  rackId: string;
  labelBy?: string | null;
  colorBy?: string | null;
  branchName: string;
  atDate?: Date | null;
}

export const rackElevationQueryKeys = {
  all: ["rack-elevation"] as const,
  kinds: (params: RackElevationKindsKeysParams) =>
    [...rackElevationQueryKeys.all, "kinds", params] as const,
  elevations: (params: Pick<RackElevationKeysParams, "rackId">) =>
    [...rackElevationQueryKeys.all, "elevation", params] as const,
  elevation: (params: RackElevationKeysParams) =>
    [...rackElevationQueryKeys.all, "elevation", params] as const,
};
