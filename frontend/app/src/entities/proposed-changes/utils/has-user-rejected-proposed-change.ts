import { User } from "@/entities/authentication/types";
import { NodeObject } from "@/entities/nodes/types";

export const hasUserRejectedProposedChange = (proposedChangesDetails: NodeObject, user: User) => {
  const usersId = proposedChangesDetails?.rejected_by?.edges?.map(
    ({ node }: { node: NodeObject }) => {
      return node.id;
    }
  );

  const hasRejected = usersId.includes(user?.id);

  return hasRejected;
};
