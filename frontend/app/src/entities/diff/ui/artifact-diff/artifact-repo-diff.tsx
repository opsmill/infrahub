import { Row } from "@/shared/components/container";
import Accordion from "@/shared/components/display/accordion";

import type { ArtifactDiff } from "@/entities/diff/domain/get-artifacts-diff";
import { DiffBadge } from "@/entities/diff/node-diff/utils";
import { ArtifactContentDiff } from "@/entities/diff/ui/artifact-diff/artifact-content-diff";

interface ArtifactRepoDiffProps {
  diff: ArtifactDiff;
}

export function ArtifactRepoDiff({ diff }: ArtifactRepoDiffProps) {
  return (
    <div className="rounded-lg bg-white p-2 text-sm shadow-sm" id={diff.id}>
      <Accordion
        title={
          <Row>
            <DiffBadge status={diff.action.toUpperCase()} />
            {diff.display_label}
          </Row>
        }
      >
        <ArtifactContentDiff
          id={diff.id}
          itemNew={diff.item_new}
          itemPrevious={diff.item_previous}
        />
      </Accordion>
    </div>
  );
}
