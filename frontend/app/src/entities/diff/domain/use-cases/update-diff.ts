import { updateDiffFromApi } from "@/entities/diff/api/update-diff-from-api";

export type UpdateDiff = (branchName: string) => Promise<void>;

export const updateDiff: UpdateDiff = async (branchName) => {
  await updateDiffFromApi({ branchName, waitUntilCompletion: true });
};
