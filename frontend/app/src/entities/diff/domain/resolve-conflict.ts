import {
  type ResolveConflictFromApiParams,
  resolveConflictFromApi,
} from "@/entities/diff/api/resolve-conflict-from-api";

export type ResolveConflict = (params: ResolveConflictFromApiParams) => Promise<void>;

export const resolveConflict: ResolveConflict = async (params) => {
  const { data, errors } = await resolveConflictFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data;
};
