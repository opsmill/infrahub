import Accordion from "@/shared/components/display/accordion";

import { ArtifactContentDiff } from "@/entities/diff/artifact-diff/artifact-content-diff";
import type { ArtifactDiff } from "@/entities/diff/domain/get-artifacts-diff";

interface ArtifactRepoDiffProps {
  diff: ArtifactDiff;
}

export function ArtifactRepoDiff({ diff }: ArtifactRepoDiffProps) {
  return (
    <div className="rounded-lg bg-white p-2 text-sm shadow-sm" id={diff.id}>
      <Accordion title={diff.display_label}>
        <ArtifactContentDiff
          id={diff.id}
          itemNew={diff.item_new}
          itemPrevious={diff.item_previous}
        />
      </Accordion>
    </div>
  );
}
