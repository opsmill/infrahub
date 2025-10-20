import { runCheckFromApi, UpdateCheckFromApiParams } from "@/entities/diff/api/run-check-from-api";

export type RunCheck = (params: UpdateCheckFromApiParams) => Promise<void>;

export const runCheck: RunCheck = async (params) => {
  await runCheckFromApi(params);
};
