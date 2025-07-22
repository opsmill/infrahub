import { User } from "@/entities/authentication/ui/useAuth";
import { NodeObject } from "@/entities/nodes/types";

export const hasUserApproved = (proposedChangesDetails: NodeObject, user: User | null) => {
  const approversId = proposedChangesDetails?.approved_by?.edges?.map(
    ({ node }: { node: NodeObject }) => {
      return node.id;
    }
  );

  const hasApproved = approversId.includes(user?.id);

  return hasApproved;
};
