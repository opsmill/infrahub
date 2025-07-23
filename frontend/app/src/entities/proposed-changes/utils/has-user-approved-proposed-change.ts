import { User } from "@/entities/authentication/ui/useAuth";
import { NodeObject } from "@/entities/nodes/types";

export const hasUserApprovedProposeChange = (proposedChangesDetails: NodeObject, user: User) => {
  const usersId = proposedChangesDetails?.approved_by?.edges?.map(
    ({ node }: { node: NodeObject }) => {
      return node.id;
    }
  );

  const hasApproved = usersId.includes(user?.id);

  return hasApproved;
};
