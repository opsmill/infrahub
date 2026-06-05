import { useOutletContext } from "react-router";

import type { GetProposedChangeDetailsResult } from "@/entities/proposed-changes/domain/get-proposed-change-details";

/**
 * Outlet context exposed to children of the proposed-change details route.
 *
 * Only enumerate fields the parent actually passes — do NOT extend
 * GetProposedChangeDetailsResult. Coupling the route context to the network
 * response shape silently leaks new query fields to every child.
 */
export interface ProposedChangeOutletContext {
  proposedChangeData: GetProposedChangeDetailsResult["proposedChangeData"];
  metadata: GetProposedChangeDetailsResult["metadata"];
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
