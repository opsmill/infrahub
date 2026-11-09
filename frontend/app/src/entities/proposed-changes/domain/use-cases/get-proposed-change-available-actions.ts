import {
  type GetProposedChangeActionFromApiParams,
  getProposedChangeAvailableActionFromApi,
  mapProposedChangeAvailableActions,
  type ProposedChangeAvailableActions,
} from "@/entities/proposed-changes/api/get-proposed-changes-available-actions-from-api";

export type GetProposedChangeAvailableActionsParams = GetProposedChangeActionFromApiParams;

export type GetProposedChangeAvailableActions = (
  params: GetProposedChangeAvailableActionsParams
) => Promise<ProposedChangeAvailableActions>;

export const getProposedChangeAvailableActions: GetProposedChangeAvailableActions = async (
  params: GetProposedChangeActionFromApiParams
) => {
  const { data, errors } = await getProposedChangeAvailableActionFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return mapProposedChangeAvailableActions(data);
};
