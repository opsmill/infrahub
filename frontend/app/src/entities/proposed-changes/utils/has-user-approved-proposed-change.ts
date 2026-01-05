import type { User } from "@/entities/authentication/types";
import type { NodeObject } from "@/entities/nodes/types";

export const hasUserApprovedProposedChange = (proposedChangesDetails: NodeObject, user: User) => {
  const usersId = proposedChangesDetails?.approved_by?.edges?.map(
    ({ node }: { node: NodeObject }) => {
      return node.id;
    }
  );

  const hasApproved = usersId.includes(user?.id);

  return hasApproved;
};
