import {
  type UpdateProposedChangeReviewFromApiParams,
  updateProposedChangeReviewFromApi,
} from "@/entities/proposed-changes/api/updateProposedChangeReviewFromApi";

export type UpdateProposedChangeReviewParams = UpdateProposedChangeReviewFromApiParams;

export type UpdateProposedChangeReview = (data: UpdateProposedChangeReviewParams) => Promise<void>;

export const updateProposedChangeReview: UpdateProposedChangeReview = async (params) => {
  const { errors } = await updateProposedChangeReviewFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }
};
