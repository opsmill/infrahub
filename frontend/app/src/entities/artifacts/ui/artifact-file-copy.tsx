import { focusVisibleStyle } from "@/shared/components/style-rac";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";
import { classNames } from "@/shared/utils/common";
import { CopyCheckIcon, CopyIcon } from "lucide-react";
import { Button } from "react-aria-components";

export function ArtifactFileCopy({ value }: { value: string }) {
  const { isCopied, copyToClipboard } = useCopyToClipboard();

  return (
    <Button
      onPress={() => copyToClipboard(value)}
      className={classNames(
        focusVisibleStyle,
        "border border-transparent p-1 hover:bg-neutral-600 rounded-lg"
      )}
    >
      {isCopied ? <CopyCheckIcon className="size-4" /> : <CopyIcon className="size-4" />}
    </Button>
  );
}
