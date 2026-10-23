import { ScrollArea } from "@infrahub/ui";

import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { getRelationshipsVisibleInTab } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-tab";
import { ObjectTaskTab, RelationshipTab } from "@/entities/nodes/object/ui/object-tabs";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { GENERIC_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import { getRepositoryInternalStatus } from "@/entities/repository/domain/rules/get-repository-internal-status";
import { RepositoryCommitsTab } from "@/entities/repository/ui/repository-commits-tab";
import { RepositoryObjectsTab } from "@/entities/repository/ui/repository-objects-tab";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { TASK_TARGET } from "@/entities/tasks/domain/model/task";

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
    <nav aria-label="Tabs" className="shrink-0">
      <Row className="items-end gap-0" data-testid="object-details-tabs">
        <ScrollArea scrollX scrollY={false} scrollBarClassName="hidden" className="min-w-0">
          <Row className={classNames("items-end gap-4 pl-4", !isRepository && "pr-4")}>
            <LinkTab to={getObjectDetailsUrl(objectKind, objectId)} scrollIntoViewOnActive>
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
        </ScrollArea>
        {isRepository && (
          // The Commits tab stays outside the scroll area so its badge is never scrolled out of view.
          <div className="shrink-0 px-4" data-testid="object-details-pinned-tab">
            <RepositoryCommitsTab
              objectKind={objectKind}
              objectId={objectId}
              internalStatus={getRepositoryInternalStatus(objectData)}
            />
          </div>
        )}
      </Row>
    </nav>
  );
}
