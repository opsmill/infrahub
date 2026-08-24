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

  // A branch name that a second, freshly fetched list also missed. One list that omits the branch
  // is not proof it is gone: the list is refetched on every branch mutation and on window focus, and
  // a live branch can be absent from a single response (a branch being deleted is filtered out for
  // the whole data delete, a follower read can lag the commit, async branch creation returns before
  // the branch is saved). A single missing response would otherwise throw the user back to the
  // homepage, off their branch, mid-work.
  const [branchConfirmedGone, setBranchConfirmedGone] = React.useState<string | null>(null);

  // Confirm the miss against a freshly fetched list before acting on it.
  React.useEffect(() => {
    if (!branches || currentBranch) return;
    // Already confirmed gone: redirect below without asking the server again.
    if (branchConfirmedGone === branchInQueryString) return;

    let abandoned = false;

    refetch()
      .then(({ data: confirmedBranches, isError }) => {
        // The user moved on, or unmounted, while the confirmation was in flight.
        if (abandoned) return;
        // A failed confirmation confirms nothing: leave the user where they are.
        if (isError) return;
        // The branch is back, so the first list was the anomaly.
        if (confirmedBranches && findSelectedBranch(confirmedBranches, branchInQueryString)) return;

        setBranchConfirmedGone(branchInQueryString);
      })
      .catch(() => {
        // Same as isError: an unconfirmed miss is not a confirmed one.
      });

    return () => {
      abandoned = true;
    };
  }, [branches, currentBranch, branchInQueryString, branchConfirmedGone, refetch]);

  // Act only on the branch the confirmation was made for, so a redirect cannot land on a user who
  // has since switched branches.
  React.useEffect(() => {
    if (!branchConfirmedGone || branchConfirmedGone !== branchInQueryString) return;

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
  }, [branchConfirmedGone, branchInQueryString, navigate]);

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
