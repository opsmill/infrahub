import { useOutletContext } from "react-router";

import type { GetProposedChangeDetailsResponse } from "@/entities/proposed-changes/domain/get-proposed-change-details";

export interface ProposedChangeOutletContext extends GetProposedChangeDetailsResponse {
  sourceBranch: string;
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
