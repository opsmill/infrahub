import { useAtom } from "jotai";
import { useQueryState } from "nuqs";
import React, { useEffect } from "react";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { DEFAULT_BRANCH_NAME } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import { currentBranchAtom } from "@/entities/branches/stores";
import { findSelectedBranch } from "@/entities/branches/utils";

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
  const [currentBranch, setCurrentBranch] = useAtom(currentBranchAtom);
  const [branchInQueryString] = useQueryState(QSP.BRANCH);
  const navigate = useNavigate();

  useEffect(() => {
    if (!branches) return;

    const selectedBranch = findSelectedBranch(branches, branchInQueryString);
    if (selectedBranch) {
      setCurrentBranch(selectedBranch);
      return;
    }

    toast(
      <Alert
        type={ALERT_TYPES.ERROR}
        message={
          <>
            Branch <b>{branchInQueryString}</b> not found, you have been redirected to the main
            branch.
          </>
        }
      />
    );
    const mainBranch = findSelectedBranch(branches, DEFAULT_BRANCH_NAME);
    setCurrentBranch(mainBranch);
    navigate("/");
  }, [branches, branchInQueryString]);

  if (isPending) {
    return <InfrahubLoading>loading branches...</InfrahubLoading>;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (currentBranch?.name !== (branchInQueryString ?? DEFAULT_BRANCH_NAME)) {
    return <InfrahubLoading>loading branches...</InfrahubLoading>;
  }

  return <BranchContext value={{ currentBranch, setCurrentBranch }}>{children}</BranchContext>;
};
