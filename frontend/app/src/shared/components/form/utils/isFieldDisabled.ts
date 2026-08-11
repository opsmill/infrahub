import type { LineageOwner } from "@/shared/api/graphql/generated/types";

import type { AuthContextType } from "@/entities/authentication/ui/auth-provider";
import type { PermissionDecisionData } from "@/entities/permission/domain/model/permission";

export type IsFieldDisabledParams = {
  owner?: Pick<LineageOwner, "id"> | null;
  auth?: Pick<AuthContextType, "user">;
  isDefaultBranch?: boolean;
  isProtected?: boolean;
  isReadOnly?: boolean;
  permissions?: { update?: PermissionDecisionData | null };
};

export const isFieldDisabled = ({
  owner,
  auth,
  isDefaultBranch,
  isProtected,
  isReadOnly,
  permissions,
}: IsFieldDisabledParams) => {
  switch (permissions?.update) {
    case "ALLOW":
      return false;
    case "ALLOW_DEFAULT":
      return !isDefaultBranch;
    case "ALLOW_OTHER":
      return !!isDefaultBranch;
    case "DENY":
      return true;
    default: {
      if (isReadOnly) return true;

      // Field is enabled if there is no owner and if is_protected is not set to true
      if (!isProtected || !owner) return false;

      // Field is available only if is_protected is set to true and if the owner is the user
      return owner?.id !== auth?.user?.id;
    }
  }
};
