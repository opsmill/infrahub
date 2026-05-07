import { useParams } from "react-router";

import { BranchDetails } from "@/entities/branches/ui/branch-details";

export function Component() {
  const { branchName } = useParams() as { branchName: string };
  return <BranchDetails branchName={branchName} />;
}
