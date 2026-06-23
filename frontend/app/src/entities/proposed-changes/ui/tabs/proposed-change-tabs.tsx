import { ScrollArea } from "@infrahub/ui";

import { Row } from "@/shared/components/container";

import { ArtifactsTab } from "./artifacts-tab";
import { ChecksTab } from "./checks-tab";
import { DataTab } from "./data-tab";
import { FilesTab } from "./files-tab";
import { OverviewTab } from "./overview-tab";
import { SchemaTab } from "./schema-tab";
import { TasksTab } from "./tasks-tab";

export interface ProposedChangeTabsProps {
  sourceBranch: string;
  proposedChangeId: string;
}

export function ProposedChangeTabs({ sourceBranch, proposedChangeId }: ProposedChangeTabsProps) {
  return (
    <ScrollArea
      scrollX
      scrollY={false}
      scrollBarClassName="hidden"
      className="shrink-0 border-gray-200 border-b"
    >
      <nav aria-label="Tabs">
        <Row className="items-end gap-4 px-4">
          <OverviewTab proposedChangeId={proposedChangeId} />
          <DataTab sourceBranch={sourceBranch} proposedChangeId={proposedChangeId} />
          <FilesTab sourceBranch={sourceBranch} proposedChangeId={proposedChangeId} />
          <ArtifactsTab sourceBranch={sourceBranch} proposedChangeId={proposedChangeId} />
          <SchemaTab sourceBranch={sourceBranch} proposedChangeId={proposedChangeId} />
          <ChecksTab proposedChangeId={proposedChangeId} />
          <TasksTab proposedChangeId={proposedChangeId} />
        </Row>
      </nav>
    </ScrollArea>
  );
}
