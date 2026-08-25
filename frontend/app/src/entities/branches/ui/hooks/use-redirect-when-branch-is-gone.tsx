import React from "react";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

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
 * Redirects to the default branch once the branch named in the URL is confirmed gone.
 *
 * One list that omits the branch is not proof of deletion: it is refetched on every branch mutation
 * and on window focus, and a live branch can be absent from a single response — filtered out while
 * its data is being deleted, missed by a lagging follower read, or not yet saved by async creation.
 * So a miss is confirmed against a second fetch, and a verdict only ever applies to the branch it
 * was reached for, for as long as no list contains that name again.
 *
 * A null branchName is the default branch (its name is absent from the URL). A confirmed-gone
 * default branch is a broken deployment: redirecting to "/" would loop, so the hook reports it as
 * `isDefaultBranchGone` for the caller to render an error instead.
 */
export function useRedirectWhenBranchIsGone({ branchName }: { branchName: string | null }) {
  const { data: branches, refetch, dataUpdatedAt } = useGetBranches();
  const navigate = useNavigate();

  const confirmedGoneNames = React.useRef(new Set<string>());
  const confirmation = React.useRef<{ branchName: string | null } | null>(null);
  const redirectedFor = React.useRef<string | null>(null);
  const [isDefaultBranchGone, setIsDefaultBranchGone] = React.useState(false);

  const isMissingFromList = !!branches && !findSelectedBranch(branches, branchName);

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

  // A name the list carries again is a name no standing verdict applies to, whichever branch the
  // user is on: a branch recreated under a deleted one's name has to be confirmed afresh.
  React.useEffect(() => {
    for (const branch of branches ?? []) {
      confirmedGoneNames.current.delete(branch.name);
    }
    if (branches?.some((branch) => branch.is_default)) {
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
  // would leave the miss unconfirmed forever, with no redirect and no recovery.
  React.useEffect(() => {
    if (!isMissingFromList) {
      confirmation.current = null;
      redirectedFor.current = null;
      return;
    }

    const alreadyConfirmedGone =
      branchName === null ? isDefaultBranchGone : confirmedGoneNames.current.has(branchName);
    if (alreadyConfirmedGone) {
      if (branchName !== null && redirectedFor.current !== branchName) {
        redirectedFor.current = branchName;
        redirectToDefaultBranch(branchName);
      }
      return;
    }

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

        confirmedGoneNames.current.add(branchName);
        redirectedFor.current = branchName;
        redirectToDefaultBranch(branchName);
      });
  }, [branchName, isMissingFromList, isDefaultBranchGone, dataUpdatedAt, refetch]);

  return { isDefaultBranchGone };
}
