import { useAtom } from "jotai";
import React, { useEffect } from "react";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";

import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { QSP } from "@/config/qsp";

import type { Branch } from "@/shared/api/graphql/generated/graphql";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useGetBranches } from "@/entities/branches/domain/get-branches.query";
import { currentBranchAtom } from "@/entities/branches/stores";
import { findSelectedBranch } from "@/entities/branches/utils";

type BranchContext = {
  currentBranch: Branch;
  setCurrentBranch: (branch: Branch) => void;
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
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
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

  if (isPending || currentBranch?.name !== (branchInQueryString ?? DEFAULT_BRANCH_NAME)) {
    return <InfrahubLoading>loading branches...</InfrahubLoading>;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return <BranchContext value={{ currentBranch, setCurrentBranch }}>{children}</BranchContext>;
};
