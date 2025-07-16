import { UpdateReviewFromApiApiParams, udpateReviewFromApi } from "../api/updateReviewFromApi";

export type UpdateReview = (data: UpdateReviewFromApiApiParams) => Promise<void>;

export const updateReview: UpdateReview = async (params) => {
  const { data, errors } = await udpateReviewFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data.CoreProposedChangeReview.object;
};
