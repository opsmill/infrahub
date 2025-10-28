import { CheckType } from "@/shared/api/graphql/generated/graphql";

import { runCheckFromApi } from "@/entities/diff/api/run-check-from-api";

export type RunCheckParams = {
  proposedChangeId: string;
  checkType: CheckType;
};
export type RunCheck = (params: RunCheckParams) => Promise<void>;

export const runCheck: RunCheck = async (params) => {
  await runCheckFromApi(params);
};
