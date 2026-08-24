import React from "react";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { findSelectedBranch } from "@/entities/branches/domain/rules/find-selected-branch";

export type BranchListConfirmation = {
  data: BranchListItem[] | undefined;
  isError: boolean;
};

const FAILED_CONFIRMATION: BranchListConfirmation = { data: undefined, isError: true };

/** Whether a freshly fetched list settles that the branch is gone. A failed fetch settles nothing. */
export function confirmsBranchIsGone(
  confirmation: BranchListConfirmation,
  branchName: string | null
): boolean {
  if (confirmation.isError || !confirmation.data) return false;

  return !findSelectedBranch(confirmation.data, branchName);
}

type UseRedirectWhenBranchIsGoneParams = {
  branchName: string | null;
  isMissingFromList: boolean;
  confirmBranchList: () => Promise<BranchListConfirmation>;
};

/**
 * Redirects to the default branch once the branch named in the URL is confirmed gone.
 *
 * One list that omits the branch is not proof of deletion: it is refetched on every branch mutation
 * and on window focus, and a live branch can be absent from a single response — filtered out while
 * its data is being deleted, missed by a lagging follower read, or not yet saved by async creation.
 * So a miss is confirmed against a second fetch, and a verdict only ever applies to the branch it
 * was reached for, for as long as that branch stays absent.
 */
export function useRedirectWhenBranchIsGone({
  branchName,
  isMissingFromList,
  confirmBranchList,
}: UseRedirectWhenBranchIsGoneParams) {
  const navigate = useNavigate();
  const confirmedGone = React.useRef(new Set<string>());

  const redirectToDefaultBranch = (goneBranchName: string) => {
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
    navigate("/");
  };

  React.useEffect(() => {
    if (branchName === null) return;

    // Seeing the branch drops the standing verdict, so a name used again is confirmed afresh.
    if (!isMissingFromList) {
      confirmedGone.current.delete(branchName);
      return;
    }

    if (confirmedGone.current.has(branchName)) {
      redirectToDefaultBranch(branchName);
      return;
    }

    let abandoned = false;

    confirmBranchList()
      .catch(() => FAILED_CONFIRMATION)
      .then((confirmation) => {
        if (abandoned || !confirmsBranchIsGone(confirmation, branchName)) return;

        confirmedGone.current.add(branchName);
        redirectToDefaultBranch(branchName);
      });

    return () => {
      abandoned = true;
    };
  }, [branchName, isMissingFromList, confirmBranchList]);
}
