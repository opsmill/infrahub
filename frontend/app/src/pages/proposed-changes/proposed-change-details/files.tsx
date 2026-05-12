import { FilesDiff } from "@/entities/diff/ui/file-diff/files-diff";
import { useProposedChangeOutlet } from "@/entities/proposed-changes/ui/use-proposed-change-outlet";

export function Component() {
  const { sourceBranch } = useProposedChangeOutlet();
  return <FilesDiff branchName={sourceBranch} />;
}
