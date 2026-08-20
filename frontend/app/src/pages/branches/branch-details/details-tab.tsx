import { BranchDetails } from "@/entities/branches/ui/branch-details";
import { useBranchDetailsOutlet } from "@/entities/branches/ui/routing/use-branch-details-outlet";

export function Component() {
  const { branch } = useBranchDetailsOutlet();
  return <BranchDetails branchName={branch.name} />;
}
