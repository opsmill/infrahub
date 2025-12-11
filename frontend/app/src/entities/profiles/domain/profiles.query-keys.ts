import type { ContextParams } from "@/shared/api/types";

import type { ProfileQueryParams } from "@/entities/profiles/types";

export interface ProfilesQueryKeysParams extends ContextParams {
  profiles: ProfileQueryParams[];
}

export const profilesQueryKeys = {
  all: ["profiles"] as const,
  allWithContext: ({ branchName, atDate }: ContextParams) =>
    [...profilesQueryKeys.all, branchName, atDate] as const,
  list: ({ branchName, atDate, profiles }: ProfilesQueryKeysParams) =>
    [
      ...profilesQueryKeys.allWithContext({ branchName, atDate }),
      profiles.map((p) => p.name).join(","),
    ] as const,
};
