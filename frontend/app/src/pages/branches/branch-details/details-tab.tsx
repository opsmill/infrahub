import { useRequiredParams } from "@/shared/hooks/use-required-params";

import { BranchDetails } from "@/entities/branches/ui/branch-details";

export function Component() {
  const { branchName } = useRequiredParams("branchName");
  return <BranchDetails branchName={branchName} />;
}
