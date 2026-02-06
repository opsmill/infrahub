import { Row } from "@/shared/components/container";
import { ScrollArea } from "@/shared/components/ui/scroll-area";

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
      <Row className="items-end gap-4 px-4" aria-label="Tabs">
        <OverviewTab />
        <DataTab sourceBranch={sourceBranch} />
        <FilesTab sourceBranch={sourceBranch} />
        <ArtifactsTab sourceBranch={sourceBranch} />
        <SchemaTab sourceBranch={sourceBranch} />
        <ChecksTab proposedChangeId={proposedChangeId} />
        <TasksTab proposedChangeId={proposedChangeId} />
      </Row>
    </ScrollArea>
  );
}
