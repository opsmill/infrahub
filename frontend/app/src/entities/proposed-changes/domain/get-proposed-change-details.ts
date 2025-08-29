import { TASK_OBJECT } from "@/config/constants";
import {
  ProposedChangeDetailsFromApiParams,
  getProposedChangeDetailsFromApi,
} from "../api/get-proposed-change-details-from-api";
import { PROPOSED_CHANGE_OBJECT } from "../constants";

export async function getProposedChangeDetails(params: ProposedChangeDetailsFromApiParams) {
  const { data, errors } = await getProposedChangeDetailsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  const edges = data?.[PROPOSED_CHANGE_OBJECT]?.edges;

  if (!edges?.length) {
    throw new Error("No proposed change found");
  }

  return {
    proposedChangeData: edges[0].node,
    tasksCount: data?.[TASK_OBJECT]?.count,
  };
}
