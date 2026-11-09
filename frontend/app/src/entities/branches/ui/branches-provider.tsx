import { useQueryState } from "nuqs";
import React from "react";
import { Navigate } from "react-router";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { QSP } from "@/shared/config/qsp";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { findSelectedBranch } from "@/entities/branches/domain/rules/find-selected-branch";
import { useConfirmBranchIsGone } from "@/entities/branches/ui/hooks/use-confirm-branch-is-gone";
import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";

type BranchContext = {
  currentBranch: BranchListItem;
  setCurrentBranch: (branch: BranchListItem) => void;
};

export const BranchContext = React.createContext<BranchContext | null>(null);

export function useCurrentBranch() {
  const context = React.use(BranchContext);
  if (!context) {
    throw new Error("useCurrentBranch must be used within a BranchesProvider.");
  }

  return context;
}

export const BranchesProvider = ({ children }: { children?: React.ReactNode }) => {
  const { data: branches, isPending, error } = useGetBranches();
  const [branchInQueryString, setBranchInQueryString] = useQueryState(QSP.BRANCH);

  const currentBranch = branches ? findSelectedBranch(branches, branchInQueryString) : null;

  const { goneBranchName, isDefaultBranchGone } = useConfirmBranchIsGone({
    branchName: branchInQueryString,
  });

  React.useEffect(() => {
    if (goneBranchName === null) return;

    toast(
      <Alert
        type={ALERT_TYPES.ERROR}
        message={
          <>
            Branch <b>{goneBranchName}</b> not found, you have been redirected to the default
            branch.
          </>
        }
      />
    );
  }, [goneBranchName]);

  // The branch QSP is the source of truth: the default branch is represented by its absence
  const setCurrentBranch = (branch: BranchListItem) => {
    setBranchInQueryString(branch.is_default ? null : branch.name);
  };

  if (isDefaultBranchGone) {
    return (
      <ErrorScreen message="The default branch is missing from this deployment. Contact your administrator." />
    );
  }

  if (goneBranchName !== null) {
    // replace, not push: Back must not land on the gone-branch URL and bounce here forever
    return <Navigate to="/" replace />;
  }

  if (isPending) {
    return <InfrahubLoading>Loading branches...</InfrahubLoading>;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (!currentBranch) {
    return <InfrahubLoading>Loading branches...</InfrahubLoading>;
  }

  return <BranchContext value={{ currentBranch, setCurrentBranch }}>{children}</BranchContext>;
};
