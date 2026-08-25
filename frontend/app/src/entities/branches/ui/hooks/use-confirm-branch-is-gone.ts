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

  const [confirmedGoneNames, setConfirmedGoneNames] = React.useState<ReadonlySet<string>>(
    new Set()
  );
  const [isDefaultBranchGone, setIsDefaultBranchGone] = React.useState(false);
  const confirmation = React.useRef<{ branchName: string | null } | null>(null);

  const isMissingFromList = !!branches && !findSelectedBranch(branches, branchName);
  const goneBranchName =
    branchName !== null && isMissingFromList && confirmedGoneNames.has(branchName)
      ? branchName
      : null;

  // A name the list carries again is a name no standing verdict applies to, whichever branch the
  // user is on: a branch recreated under a deleted one's name has to be confirmed afresh.
  React.useEffect(() => {
    if (!branches) return;

    setConfirmedGoneNames((previous) => {
      const carried = branches.filter((branch) => previous.has(branch.name));
      if (carried.length === 0) return previous;

      const next = new Set(previous);
      for (const branch of carried) {
        next.delete(branch.name);
      }
      return next;
    });

    if (branches.some((branch) => branch.is_default)) {
      setIsDefaultBranchGone(false);
    }
  }, [branches]);

  React.useEffect(
    () => () => {
      confirmation.current = null;
    },
    []
  );

  // dataUpdatedAt is a dependency so that every newly arrived list that still omits the branch gets
  // its own confirmation attempt: retries are off app-wide, so without it one failed confirmation
  // would leave the miss unconfirmed forever, with no verdict and no recovery.
  React.useEffect(() => {
    if (!isMissingFromList) {
      confirmation.current = null;
      return;
    }

    const alreadyConfirmedGone =
      branchName === null ? isDefaultBranchGone : confirmedGoneNames.has(branchName);
    if (alreadyConfirmedGone) return;

    if (confirmation.current?.branchName === branchName) return;

    const attempt = { branchName };
    confirmation.current = attempt;

    refetch()
      .catch(() => FAILED_CONFIRMATION)
      .then((confirmed) => {
        // A verdict is discarded once its attempt is superseded or abandoned.
        if (confirmation.current !== attempt) return;
        confirmation.current = null;

        if (!confirmsBranchIsGone(confirmed, branchName)) return;

        if (branchName === null) {
          setIsDefaultBranchGone(true);
          return;
        }

        setConfirmedGoneNames((previous) => new Set(previous).add(branchName));
      });
  }, [
    branchName,
    isMissingFromList,
    isDefaultBranchGone,
    confirmedGoneNames,
    dataUpdatedAt,
    refetch,
  ]);

  return { goneBranchName, isDefaultBranchGone };
}
