import { AuthContextType } from "@/hooks/useAuth";
import { LineageOwner } from "@/generated/graphql";

type getIsDisabledParams = {
  owner?: LineageOwner | null;
  user?: AuthContextType;
  isProtected?: boolean;
  isReadOnly?: boolean;
};

export const getIsDisabled = ({ owner, user, isProtected, isReadOnly }: getIsDisabledParams) => {
  // Field is read only
  if (isReadOnly) return true;

  // Field is available if there is no owner and if is_protected is not set to true
  if (!isProtected || !owner || user?.permissions?.isAdmin) return false;

  // Field is available only if is_protected is set to true and if the owner is the user
  return owner?.id !== user?.data?.sub;
};
