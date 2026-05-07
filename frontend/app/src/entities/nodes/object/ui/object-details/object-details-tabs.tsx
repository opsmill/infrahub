import { ScrollArea } from "@infrahub/ui";

import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";
import { GENERIC_REPOSITORY_KIND, TASK_TARGET } from "@/shared/config/constants";

import { ObjectTaskTab, RelationshipTab } from "@/entities/nodes/object/ui/object-tabs";
import { getRelationshipsVisibleInTab } from "@/entities/nodes/object/utils/get-relationships-visible-in-tab";
import type { NodeObject } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { RepositoryObjectsTab } from "@/entities/repository/ui/repository-objects-tab";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

interface ObjectDetailsTabsProps {
  objectSchema: ModelSchema;
  objectData: NodeObject;
}

export function ObjectDetailsTabs({ objectSchema, objectData }: ObjectDetailsTabsProps) {
  const objectId = objectData.id;
  const objectKind = objectData.__typename;
  const relationshipsTabs = getRelationshipsVisibleInTab(objectSchema.relationships ?? []);
  const isTaskTarget = isOfKind(TASK_TARGET, objectSchema);
  const isRepository = isOfKind(GENERIC_REPOSITORY_KIND, objectSchema);

  return (
    <ScrollArea scrollX scrollY={false} scrollBarClassName="hidden" className="shrink-0">
      <nav aria-label="Tabs">
        <Row className="items-end gap-4 px-4" data-testid="object-details-tabs">
          <LinkTab href={getObjectDetailsUrl(objectKind, objectId)} scrollIntoViewOnActive>
            Details
          </LinkTab>
          {relationshipsTabs.map((tab) => (
            <RelationshipTab
              key={tab.name}
              objectKind={objectKind}
              objectId={objectId}
              relationshipSchema={tab}
            />
          ))}
          {isTaskTarget && <ObjectTaskTab objectKind={objectKind} objectId={objectId} />}
          {isRepository && <RepositoryObjectsTab objectKind={objectKind} objectId={objectId} />}
        </Row>
      </nav>
    </ScrollArea>
  );
}
