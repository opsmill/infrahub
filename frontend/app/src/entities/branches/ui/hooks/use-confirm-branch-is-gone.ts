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
 * Confirms whether the branch named in the URL is really gone before anyone acts on its absence.
 *
 * One list that omits the branch is not proof of deletion: it is refetched on every branch mutation
 * and on window focus, and a live branch can be absent from a single response — filtered out while
 * its data is being deleted, missed by a lagging follower read, or not yet saved by async creation.
 * So a miss is confirmed against a second fetch, and a verdict only ever applies to the branch it
 * was reached for, for as long as no list contains that name again.
 *
 * A null branchName is the default branch (its name is absent from the URL). Its confirmed absence
 * is a broken deployment, reported separately so the caller can render an error instead of
 * redirecting onto the very branch that is missing.
 */
export function useConfirmBranchIsGone({ branchName }: { branchName: string | null }) {
  const { data: branches, refetch, dataUpdatedAt } = useGetBranches();

  // The one standing verdict: a branch identity a confirming fetch has settled as gone.
  const [confirmedGone, setConfirmedGone] = React.useState<{
    branchName: string | null;
  } | null>(null);
  const pendingConfirmation = React.useRef<{ branchName: string | null } | null>(null);

  // A branch the list carries again has no standing verdict: a branch recreated under a deleted
  // one's name has to be confirmed afresh.
  if (confirmedGone && branches && findSelectedBranch(branches, confirmedGone.branchName)) {
    setConfirmedGone(null);
  }

  const isMissingFromList = !!branches && !findSelectedBranch(branches, branchName);
  const isConfirmedGone =
    isMissingFromList && !!confirmedGone && confirmedGone.branchName === branchName;

  // dataUpdatedAt is a dependency so that every newly arrived list that still omits the branch gets
  // its own confirmation attempt: retries are off app-wide, so without it one failed confirmation
  // would leave the miss unconfirmed forever, with no verdict and no recovery.
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
        // A verdict is discarded once its attempt is superseded or abandoned.
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
