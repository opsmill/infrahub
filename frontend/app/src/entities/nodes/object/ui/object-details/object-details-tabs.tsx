import { useQueryState } from "nuqs";

import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { GENERIC_REPOSITORY_KIND, TASK_TARGET } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import { ObjectDetailsTab, RelationshipTab } from "@/entities/nodes/object/ui/object-tabs";
import { getRelationshipsVisibleInTab } from "@/entities/nodes/object/utils/get-relationships-visible-in-tab";
import { ActionButtons } from "@/entities/nodes/object-item-details/action-buttons";
import type { NodeObject } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { Permission } from "@/entities/permission/types";
import { RepositoryObjectsTab } from "@/entities/repository/ui/repository-objects-tab";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";
import { ObjectTaskTab } from "@/entities/tasks/ui/task-tab";

interface ObjectDetailsTabsProps {
  schema: ModelSchema;
  objectData: NodeObject;
  permission: Permission;
}

export function ObjectDetailsTabs({ schema, objectData, permission }: ObjectDetailsTabsProps) {
  const [qspTab] = useQueryState(QSP.TAB);

  const isTaskTarget = isOfKind(TASK_TARGET, schema);
  const isRepository = isOfKind(GENERIC_REPOSITORY_KIND, schema);

  const relationshipsTabs = getRelationshipsVisibleInTab(schema.relationships ?? []);

  const objectId = objectData.id;
  const objectKind = objectData.__typename;

  return (
    <header className="flex items-center border-gray-200 border-b px-2">
      <ScrollArea scrollX scrollBarClassName="hidden" className="grow">
        <div className="flex grow gap-8 px-4" data-testid="object-details-tabs">
          <ObjectDetailsTab
            isActive={!qspTab}
            to={getObjectDetailsUrl(objectKind as string, objectData.id)}
          >
            {schema.label}
          </ObjectDetailsTab>
          {relationshipsTabs.map((tab) => {
            return (
              <RelationshipTab
                key={tab.name}
                objectKind={objectKind as string}
                objectId={objectId}
                relationshipSchema={tab as RelationshipSchema}
              />
            );
          })}
          {isTaskTarget && <ObjectTaskTab objectId={objectId} />}
          {isRepository && <RepositoryObjectsTab objectId={objectId} />}
        </div>
      </ScrollArea>

      <ActionButtons schema={schema} objectDetailsData={objectData} permission={permission} />
    </header>
  );
}
