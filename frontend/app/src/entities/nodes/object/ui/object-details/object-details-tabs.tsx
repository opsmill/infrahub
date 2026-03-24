import { useQueryState } from "nuqs";

import { Row } from "@/shared/components/container";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { GENERIC_REPOSITORY_KIND, TASK_TARGET } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import { ObjectDetailsTab, RelationshipTab } from "@/entities/nodes/object/ui/object-tabs";
import { getRelationshipsVisibleInTab } from "@/entities/nodes/object/utils/get-relationships-visible-in-tab";
import type { NodeObject } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { RepositoryObjectsTab } from "@/entities/repository/ui/repository-objects-tab";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";
import { ObjectTaskTab } from "@/entities/tasks/ui/task-tab";

interface ObjectDetailsTabsProps {
  objectSchema: ModelSchema;
  objectData: NodeObject;
}

export function ObjectDetailsTabs({ objectSchema, objectData }: ObjectDetailsTabsProps) {
  const [qspTab] = useQueryState(QSP.TAB);

  const objectId = objectData.id;
  const objectKind = objectData.__typename;
  const relationshipsTabs = getRelationshipsVisibleInTab(objectSchema.relationships ?? []);
  const isTaskTarget = isOfKind(TASK_TARGET, objectSchema);
  const isRepository = isOfKind(GENERIC_REPOSITORY_KIND, objectSchema);

  return (
    <ScrollArea
      scrollX
      scrollY={false}
      scrollBarClassName="hidden"
      className="shrink-0 border-gray-200 border-b"
    >
      <Row className="items-end gap-4 px-3" data-testid="object-details-tabs">
        <ObjectDetailsTab isActive={!qspTab} to={getObjectDetailsUrl(objectKind, objectData.id)}>
          Details
        </ObjectDetailsTab>
        {relationshipsTabs.map((tab) => {
          return (
            <RelationshipTab
              key={tab.name}
              objectKind={objectKind}
              objectId={objectId}
              relationshipSchema={tab}
            />
          );
        })}
        {isTaskTarget && <ObjectTaskTab objectId={objectId} />}
        {isRepository && <RepositoryObjectsTab objectId={objectId} />}
      </Row>
    </ScrollArea>
  );
}
