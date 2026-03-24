import Accordion from "@/shared/components/display/accordion";

import type { FileDiff } from "@/entities/diff/domain/get-files-diff";
import { FileContentDiff } from "@/entities/diff/ui/file-diff/file-content-diff";

interface FileRepoDiffProps {
  diff: FileDiff;
}

export function FileRepoDiff({ diff }: FileRepoDiffProps) {
  const { files = [] } = diff;

  return (
    <div className="rounded-lg bg-white p-2 text-sm shadow-sm">
      <Accordion title={diff.display_name}>
        {files.map((file) => (
          <FileContentDiff
            key={file.location}
            repositoryId={diff.id}
            repositoryDisplayName={diff.display_name}
            file={file}
            commitFrom={diff.commit_from}
            commitTo={diff.commit_to}
          />
        ))}
      </Accordion>
    </div>
  );
}
