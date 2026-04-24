import type { User } from "@/entities/authentication/types";
import type { ProposedChangeDetail } from "@/entities/proposed-changes/domain/proposed-change.types";

export const hasUserRejectedProposedChange = (
  proposedChangesDetails: ProposedChangeDetail,
  user: User
) => {
  const usersId = proposedChangesDetails.rejected_by?.edges?.map(({ node }) => node?.id);

  return usersId?.includes(user?.id) ?? false;
};
