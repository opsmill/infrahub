import { useRequiredParams } from "@/shared/hooks/use-required-params";

import { FilesDiff } from "@/entities/diff/ui/file-diff/files-diff";

export function Component() {
  const { branchName } = useRequiredParams("branchName");
  return <FilesDiff branchName={branchName} />;
}
