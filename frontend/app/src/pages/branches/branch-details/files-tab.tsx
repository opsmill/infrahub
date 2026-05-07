import { useBranchDetailsOutlet } from "@/entities/branches/ui/use-branch-details-outlet";
import { FilesDiff } from "@/entities/diff/ui/file-diff/files-diff";

export function Component() {
  const { branch } = useBranchDetailsOutlet();
  return <FilesDiff branchName={branch.name} />;
}
