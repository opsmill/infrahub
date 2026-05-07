import { useOutletContext } from "react-router";

import type { GetProposedChangeDetailsResponse } from "@/entities/proposed-changes/domain/get-proposed-change-details";

/**
 * Outlet context exposed to children of the proposed-change details route.
 *
 * Only enumerate fields the parent actually passes — do NOT extend
 * GetProposedChangeDetailsResponse. Coupling the route context to the network
 * response shape silently leaks new query fields to every child.
 */
export interface ProposedChangeOutletContext {
  proposedChangeData: GetProposedChangeDetailsResponse["proposedChangeData"];
  metadata: GetProposedChangeDetailsResponse["metadata"];
  sourceBranch: string;
  destinationBranch: string;
}

export function useProposedChangeOutlet(): ProposedChangeOutletContext {
  const context = useOutletContext<ProposedChangeOutletContext | null>();
  if (!context) {
    throw new Error(
      "useProposedChangeOutlet must be used inside the proposed-change parent route's <Outlet>"
    );
  }
  return context;
}
