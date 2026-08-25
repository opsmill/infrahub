import React from "react";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { findSelectedBranch } from "@/entities/branches/domain/rules/find-selected-branch";
import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";

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

/**
 * Confirms against a second fetch that the branch named in the URL is really gone — a single list
 * omitting a branch is not proof of deletion, since a live branch can be absent from one response.
 * A null branchName is the default branch; its confirmed absence is reported as
 * `isDefaultBranchGone` so the caller can render an error instead of redirecting in a loop.
 */
export function useConfirmBranchIsGone({ branchName }: { branchName: string | null }) {
  const { data: branches, refetch, dataUpdatedAt } = useGetBranches();

  const [confirmedGone, setConfirmedGone] = React.useState<{
    branchName: string | null;
  } | null>(null);
  const pendingConfirmation = React.useRef<{ branchName: string | null } | null>(null);

  // A branch the list carries again has to be confirmed afresh, so its standing verdict is dropped.
  if (confirmedGone && branches && findSelectedBranch(branches, confirmedGone.branchName)) {
    setConfirmedGone(null);
  }

  const isMissingFromList = !!branches && !findSelectedBranch(branches, branchName);
  const isConfirmedGone =
    isMissingFromList && !!confirmedGone && confirmedGone.branchName === branchName;

  // dataUpdatedAt re-arms the confirmation on every fresh list, since retries are off app-wide.
  React.useEffect(() => {
    if (!isMissingFromList) {
      pendingConfirmation.current = null;
      return;
    }

    if (isConfirmedGone) return;
    if (pendingConfirmation.current?.branchName === branchName) return;

    const attempt = { branchName };
    pendingConfirmation.current = attempt;

    refetch()
      .catch(() => FAILED_CONFIRMATION)
      .then((confirmed) => {
        // A superseded or abandoned attempt's verdict no longer applies.
        if (pendingConfirmation.current !== attempt) return;
        pendingConfirmation.current = null;

        if (!confirmsBranchIsGone(confirmed, branchName)) return;

        setConfirmedGone({ branchName });
      });
  }, [branchName, isMissingFromList, isConfirmedGone, dataUpdatedAt, refetch]);

  return {
    goneBranchName: isConfirmedGone && branchName !== null ? branchName : null,
    isDefaultBranchGone: isConfirmedGone && branchName === null,
  };
}
