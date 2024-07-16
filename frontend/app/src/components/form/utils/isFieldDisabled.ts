import { LineageOwner } from "@/generated/graphql";
import { AuthContextType } from "@/hooks/useAuth";

export type IsFieldDisabledParams = {
  owner?: LineageOwner | null;
  auth?: AuthContextType;
  isProtected?: boolean;
  isReadOnly?: boolean;
};

export const isFieldDisabled = ({
  owner,
  auth,
  isProtected,
  isReadOnly,
}: IsFieldDisabledParams) => {
  if (isReadOnly) return true;

  // Field is available if there is no owner and if is_protected is not set to true
  if (!isProtected || !owner || auth?.permissions?.isAdmin) return false;

  // Field is available only if is_protected is set to true and if the owner is the user
  return owner?.id !== auth?.user?.id;
};
