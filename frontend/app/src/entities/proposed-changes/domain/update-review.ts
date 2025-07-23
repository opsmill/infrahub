import {
  UpdateReviewFromApiApiParams,
  updateProposedCHangeReviewFromApi,
} from "../api/updateProposedCHangeReviewFromApi";

export type UpdateReview = (data: UpdateReviewFromApiApiParams) => Promise<void>;

export const updateReview: UpdateReview = async (params) => {
  const { data, errors } = await updateProposedCHangeReviewFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data.CoreProposedChangeReview.object;
};
