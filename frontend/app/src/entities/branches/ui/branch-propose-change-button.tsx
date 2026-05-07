import { LinkButton } from "@infrahub/ui";
import { PlusIcon } from "lucide-react";

import { BranchStatus } from "@/shared/api/graphql/generated/types";
import { constructPath } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";

type BranchProposeChangeButtonProps = {
  branch: BranchDetail;
};

export const BranchProposeChangeButton = ({ branch }: BranchProposeChangeButtonProps) => {
  const { isAuthenticated } = useAuth();

  const isDisabled =
    !isAuthenticated || !!branch.is_default || branch.status === BranchStatus.MERGED;

  return (
    <LinkButton
      isDisabled={isDisabled}
      href={constructPath("/proposed-changes/new", [
        { name: QSP.SOURCE_BRANCH, value: branch.name },
      ])}
    >
      Propose change
      <PlusIcon className="h-4 w-4" aria-hidden="true" />
    </LinkButton>
  );
};
