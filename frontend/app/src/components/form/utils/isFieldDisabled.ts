import { LineageOwner } from "@/generated/graphql";
import { AuthContextType } from "@/hooks/useAuth";
import { PermissionDecisionData } from "@/screens/permission/types";
import { store } from "@/state";
import { currentBranchAtom } from "@/state/atoms/branches.atom";

export type IsFieldDisabledParams = {
  owner?: LineageOwner | null;
  auth?: AuthContextType;
  isProtected?: boolean;
  isReadOnly?: boolean;
  permissions?: { update?: PermissionDecisionData | null };
};

export const isFieldDisabled = ({
  owner,
  auth,
  isProtected,
  isReadOnly,
  permissions,
}: IsFieldDisabledParams) => {
  const currentBranch = store.get(currentBranchAtom);

  switch (permissions?.update) {
    case "ALLOW":
      return false;
    case "ALLOW_DEFAULT":
      return !currentBranch?.is_default;
    case "ALLOW_OTHER":
      return !!currentBranch?.is_default;
    case "DENY":
      return true;
    default: {
      if (isReadOnly) return true;

      // Field is available if there is no owner and if is_protected is not set to true
      if (!isProtected || !owner) return false;

      // Field is available only if is_protected is set to true and if the owner is the user
      return owner?.id !== auth?.user?.id;
    }
  }
};
