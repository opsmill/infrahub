import {
  GetProposedChangeActionFromApiParams,
  getProposedChangeAvailableActionFromApi,
} from "../api/get-proposed-changes-available-actions-from-api";

export async function getProposedChangeAvailableActions(
  params: GetProposedChangeActionFromApiParams
) {
  const { data, errors } = await getProposedChangeAvailableActionFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data.CoreProposedChangeAvailableActions.edges.reduce((acc, edge) => {
    return {
      ...acc,
      [edge.node.action]: edge.node,
    };
  }, {});
}
