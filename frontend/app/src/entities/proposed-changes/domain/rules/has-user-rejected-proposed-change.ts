import type { User } from "@/entities/authentication/domain/model/user";
import type { ProposedChangeDetail } from "@/entities/proposed-changes/domain/model/proposed-change";

export const hasUserRejectedProposedChange = (
  proposedChangesDetails: ProposedChangeDetail,
  user: User
) => {
  const usersId = proposedChangesDetails.rejected_by?.edges?.map(({ node }) => node?.id);

  return usersId?.includes(user?.id) ?? false;
};
