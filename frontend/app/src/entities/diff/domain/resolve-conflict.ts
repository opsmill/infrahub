import { ConflictSelection } from "@/shared/api/graphql/generated/graphql";

import { resolveConflictFromApi } from "@/entities/diff/api/resolve-conflict-from-api";

export type ResolveConflictParams = {
  id: string;
  selection: ConflictSelection;
};

export type ResolveConflict = (params: ResolveConflictParams) => Promise<void>;

export const resolveConflict: ResolveConflict = async (params) => {
  await resolveConflictFromApi(params);
};
