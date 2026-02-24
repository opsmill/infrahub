import { PlusIcon } from "lucide-react";

import { constructPath } from "@/shared/api/rest/fetch";
import { LinkButton } from "@/shared/components/ui/button";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { BRANCH_STATUS } from "@/entities/branches/constants";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";

type BranchProposeChangeButtonProps = {
  branch: BranchDetail;
};

export const BranchProposeChangeButton = ({ branch }: BranchProposeChangeButtonProps) => {
  const { isAuthenticated } = useAuth();

  const isMerged = branch.status === BRANCH_STATUS.MERGED;
  const isDisabled = !isAuthenticated || !!branch.is_default || isMerged;

  return (
    <LinkButton
      onClick={(event) => {
        if (isDisabled) {
          event?.preventDefault();
        }
      }}
      className={classNames(isDisabled && "cursor-not-allowed opacity-50")}
      to={constructPath("/proposed-changes/new", [{ name: QSP.SOURCE_BRANCH, value: branch.name }])}
    >
      Propose change
      <PlusIcon className="ml-2 h-4 w-4" aria-hidden="true" />
    </LinkButton>
  );
};
