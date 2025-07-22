import { User } from "@/entities/authentication/ui/useAuth";
import { NodeObject } from "@/entities/nodes/types";

export const hasUserRejected = (proposedChangesDetails: NodeObject, user: User | null) => {
  const usersId = proposedChangesDetails?.rejected_by?.edges?.map(
    ({ node }: { node: NodeObject }) => {
      return node.id;
    }
  );

  const hasRejected = usersId.includes(user?.id);

  return hasRejected;
};
