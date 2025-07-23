import {
  UpdateReviewFromApiApiParams,
  updateProposedChangeReviewFromApi,
} from "../api/updateProposedChangeReviewFromApi";

export type UpdateReview = (data: UpdateReviewFromApiApiParams) => Promise<void>;

export const updateProposedChangeReview: UpdateReview = async (params) => {
  const { data, errors } = await updateProposedChangeReviewFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data.CoreProposedChangeReview.object;
};
