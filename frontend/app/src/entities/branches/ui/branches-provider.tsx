import { useQueryState } from "nuqs";
import React from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { QSP } from "@/shared/config/qsp";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { findSelectedBranch } from "@/entities/branches/domain/rules/find-selected-branch";
import { useRedirectWhenBranchIsGone } from "@/entities/branches/ui/hooks/use-redirect-when-branch-is-gone";
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
  const { data: branches, isPending, error, refetch } = useGetBranches();
  const [branchInQueryString, setBranchInQueryString] = useQueryState(QSP.BRANCH);

  const currentBranch = branches ? findSelectedBranch(branches, branchInQueryString) : null;

  // The branch QSP is the source of truth: the default branch is represented by its absence
  const setCurrentBranch = (branch: BranchListItem) => {
    setBranchInQueryString(branch.is_default ? null : branch.name);
  };

  useRedirectWhenBranchIsGone({
    branchName: branchInQueryString,
    isMissingFromList: !!branches && !currentBranch,
    confirmBranchList: refetch,
  });

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
