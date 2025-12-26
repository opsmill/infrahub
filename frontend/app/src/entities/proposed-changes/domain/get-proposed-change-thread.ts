import { PROPOSED_CHANGES_THREAD_OBJECT } from "@/shared/config/constants";

import {
  getProposedChangeThreadFromApi,
  type ProposedChangeThreadFromApiParams,
} from "@/entities/proposed-changes/api/get-proposed-change-thread-from-api";

export type GetProposedChangeThreadParams = ProposedChangeThreadFromApiParams;

export const getProposedChangeThread = async (params: GetProposedChangeThreadParams) => {
  const { data, errors } = await getProposedChangeThreadFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const node = data?.[PROPOSED_CHANGES_THREAD_OBJECT]?.edges?.[0];

  if (!node) {
    throw new Error("No thread data found");
  }

  return node;
};
