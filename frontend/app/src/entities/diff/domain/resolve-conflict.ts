import { resolveConflictFromApi } from "../api/resolve-conflict-from-api";

export type ResolveConflictParams = {
  id: string;
  selection: string | null;
};

export type ResolveConflict = (params: ResolveConflictParams) => Promise<void>;

export const resolveConflict: ResolveConflict = async (params) => {
  await resolveConflictFromApi(params);
};
