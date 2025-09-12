import { CopyCheckIcon, CopyIcon } from "lucide-react";

import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

import { ArtifactFileButton } from "@/entities/artifacts/ui/artifact-file-button";

export function ArtifactFileCopy({ value }: { value: string }) {
  const { isCopied, copyToClipboard } = useCopyToClipboard();

  return (
    <ArtifactFileButton onPress={() => copyToClipboard(value)}>
      {isCopied ? <CopyCheckIcon className="size-4" /> : <CopyIcon className="size-4" />}
    </ArtifactFileButton>
  );
}
