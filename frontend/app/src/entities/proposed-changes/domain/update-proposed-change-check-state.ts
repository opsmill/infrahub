import {
  updateProposedChangeCheckStateFromApi,
  updateProposedChangeCheckStateFromApiParams,
} from "../api/update-proposed-check-state-from-api";

export type UpdateProposedChangeCheckStateParams = updateProposedChangeCheckStateFromApiParams;

export type UpdateProposedChangeCheckState = (
  data: UpdateProposedChangeCheckStateParams
) => Promise<void>;

export const updateProposedChangeCheckState: UpdateProposedChangeCheckState = async (params) => {
  const { data, errors } = await updateProposedChangeCheckStateFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data.CoreProposedChangeReview.object;
};
