import { useAtom } from "jotai";
import { useQueryState } from "nuqs";
import React, { useEffect } from "react";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { QSP } from "@/shared/config/qsp";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { DEFAULT_BRANCH_NAME } from "@/entities/branches/domain/model/branch";
import { findSelectedBranch } from "@/entities/branches/domain/rules/find-selected-branch";
import { currentBranchAtom } from "@/entities/branches/stores";
import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";

type BranchContext = {
  currentBranch: BranchListItem;
  /**
   * Targets a branch for the whole session. The query string is the source of truth and the atom is
   * derived from it, so both must move together — writing the atom alone strands the provider on its
   * loading guard.
   */
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
  const [currentBranch, setCurrentBranchAtom] = useAtom(currentBranchAtom);
  const [branchInQueryString, setBranchInQueryString] = useQueryState(QSP.BRANCH);
  const navigate = useNavigate();

  function setCurrentBranch(branch: BranchListItem) {
    // The default branch is represented by an absent query string, not by its name.
    setBranchInQueryString(branch.is_default ? null : branch.name);
    setCurrentBranchAtom(branch);
  }

  useEffect(() => {
    if (!branches) return;

    // Mirrors the query string into the atom, so it writes the atom only — going through
    // setCurrentBranch here would have the effect steering the value it reacts to.
    const selectedBranch = findSelectedBranch(branches, branchInQueryString);
    if (selectedBranch) {
      setCurrentBranchAtom(selectedBranch);
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
    setCurrentBranchAtom(mainBranch);
    navigate("/");
  }, [branches, branchInQueryString]);

  if (isPending) {
    return <InfrahubLoading>Loading branches...</InfrahubLoading>;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (currentBranch?.name !== (branchInQueryString ?? DEFAULT_BRANCH_NAME)) {
    return <InfrahubLoading>Loading branches...</InfrahubLoading>;
  }

  return <BranchContext value={{ currentBranch, setCurrentBranch }}>{children}</BranchContext>;
};
