import { useOutletContext } from "react-router";

import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";

export interface BranchDetailsOutletContext {
  branch: BranchListItem;
}

export function useBranchDetailsOutlet(): BranchDetailsOutletContext {
  const context = useOutletContext<BranchDetailsOutletContext | null>();
  if (!context) {
    throw new Error(
      "useBranchDetailsOutlet must be used inside the branch details parent route's <Outlet>"
    );
  }
  return context;
}
