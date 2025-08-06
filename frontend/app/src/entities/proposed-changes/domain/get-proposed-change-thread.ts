import { PROPOSED_CHANGES_THREAD_OBJECT } from "@/config/constants";
import {
  ProposedChangeThreadFromApiParams,
  getProposedChangeThreadFromApi,
} from "../api/get-proposed-change-thread-from-api";

export async function getProposedChangeThread(params: ProposedChangeThreadFromApiParams) {
  const { data, errors } = await getProposedChangeThreadFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data[PROPOSED_CHANGES_THREAD_OBJECT].edges[0].node;
}
