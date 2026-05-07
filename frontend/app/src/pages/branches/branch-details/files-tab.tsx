import { useParams } from "react-router";

import { FilesDiff } from "@/entities/diff/ui/file-diff/files-diff";

export function Component() {
  const { branchName } = useParams() as { branchName: string };
  return <FilesDiff branchName={branchName} />;
}
