import { useQueryState } from "nuqs";
import React from "react";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { QSP } from "@/shared/config/qsp";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { findSelectedBranch } from "@/entities/branches/domain/rules/find-selected-branch";
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
  const navigate = useNavigate();

  const currentBranch = branches ? findSelectedBranch(branches, branchInQueryString) : null;

  // The branch QSP is the source of truth: the default branch is represented by its absence
  const setCurrentBranch = (branch: BranchListItem) => {
    setBranchInQueryString(branch.is_default ? null : branch.name);
  };

  // Tracks the branch a fetched list already missed, so a single confirmation is in flight at a time.
  const missToConfirm = React.useRef<string | null | undefined>(undefined);

  React.useEffect(() => {
    if (!branches || currentBranch) return;
    if (missToConfirm.current === branchInQueryString) return;

    missToConfirm.current = branchInQueryString;

    // One list that omits the branch is not proof the branch is gone. The list is refetched on every
    // branch mutation and on window focus, so a single response that misses a live branch would
    // otherwise throw the user back to the homepage, off their branch, mid-work. Confirm the miss
    // against a freshly fetched list first — a branch that really was deleted is missing from that
    // one too, so the redirect still happens, one request later.
    refetch().then(({ data: confirmedBranches, isError }) => {
      const branchIsBack =
        !!confirmedBranches && !!findSelectedBranch(confirmedBranches, branchInQueryString);

      // A failed confirmation confirms nothing: leave the user where they are.
      if (branchIsBack || isError) {
        missToConfirm.current = undefined;
        return;
      }

      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={
            <>
              Branch <b>{branchInQueryString}</b> not found, you have been redirected to the default
              branch.
            </>
          }
        />
      );
      navigate("/");
    });
  }, [branches, currentBranch, branchInQueryString]);

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
