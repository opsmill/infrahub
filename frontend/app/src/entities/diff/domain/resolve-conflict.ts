import {
  ResolveConflictFromApiParams,
  resolveConflictFromApi,
} from "@/entities/diff/api/resolve-conflict-from-api";

export type ResolveConflict = (params: ResolveConflictFromApiParams) => Promise<void>;

export const resolveConflict: ResolveConflict = async (params) => {
  await resolveConflictFromApi(params);
};
