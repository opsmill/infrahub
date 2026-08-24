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
 * One list that omits the branch is not proof of deletion: the list is refetched on every branch
 * mutation and on window focus, and a live branch can be absent from a single response — it is
 * filtered out for as long as its data is being deleted, a follower read can lag the commit, and
 * async creation returns before the branch is saved. So a miss is confirmed against a second fetch
 * before the user loses their page, and the verdict is tied to the branch it was reached for.
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

  // `navigate` and `redirectToDefaultBranch` are deliberately not dependencies: react-router
  // rebuilds `navigate` on every navigation, so depending on it would re-run this effect after its
  // own redirect and toast twice. Redirecting to an absolute path does not need a current one.
  React.useEffect(() => {
    if (!isMissingFromList || branchName === null) return;

    if (confirmedGone.current.has(branchName)) {
      redirectToDefaultBranch(branchName);
      return;
    }

    let abandoned = false;

    confirmBranchList()
      .then((confirmation) => {
        if (abandoned || !confirmsBranchIsGone(confirmation, branchName)) return;

        confirmedGone.current.add(branchName);
        redirectToDefaultBranch(branchName);
      })
      .catch(() => {});

    // The user left the branch being confirmed, so its verdict no longer applies to them.
    return () => {
      abandoned = true;
    };
  }, [branchName, isMissingFromList, confirmBranchList]);
}
