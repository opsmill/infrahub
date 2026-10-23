import { ScrollArea } from "@infrahub/ui";
import { type ReactNode, type RefObject, useEffect, useRef, useState } from "react";

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

  const scrolledTabs = (
    <>
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
    </>
  );

  if (isRepository) {
    return (
      <TabsWithPinnedLastTab
        lastTab={
          <RepositoryCommitsTab
            objectKind={objectKind}
            objectId={objectId}
            internalStatus={getRepositoryInternalStatus(objectData)}
          />
        }
      >
        {scrolledTabs}
      </TabsWithPinnedLastTab>
    );
  }

  return (
    <ScrollArea scrollX scrollY={false} scrollBarClassName="hidden" className="shrink-0">
      <nav aria-label="Tabs">
        <Row className="items-end gap-4 px-4" data-testid="object-details-tabs">
          {scrolledTabs}
        </Row>
      </nav>
    </ScrollArea>
  );
}

// The last tab sits outside the scroll area so its signal is never scrolled away.
function TabsWithPinnedLastTab({ children, lastTab }: { children: ReactNode; lastTab: ReactNode }) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const clippedEdges = useClippedEdges(viewportRef);

  return (
    <nav aria-label="Tabs" className="shrink-0">
      <Row className="items-end gap-0" data-testid="object-details-tabs">
        <ScrollArea
          ref={viewportRef}
          scrollX
          scrollY={false}
          scrollBarClassName="hidden"
          // A mask, not a colour overlay, fades a clipped edge because the card background is a gradient.
          className={classNames(
            "min-w-0 shrink",
            clippedEdges.start && "mask-l-from-95%",
            clippedEdges.end && "mask-r-from-95%"
          )}
        >
          <Row className="items-end gap-4 pl-4">{children}</Row>
        </ScrollArea>
        <Row className="shrink-0 px-4" data-testid="object-details-pinned-tab">
          {lastTab}
        </Row>
      </Row>
    </nav>
  );
}

interface ClippedEdges {
  start: boolean;
  end: boolean;
}

function useClippedEdges(viewportRef: RefObject<HTMLDivElement | null>): ClippedEdges {
  const [clippedEdges, setClippedEdges] = useState<ClippedEdges>({ start: false, end: false });

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    const update = () => {
      const start = viewport.scrollLeft > 1;
      const end = viewport.scrollWidth - viewport.clientWidth - viewport.scrollLeft > 1;
      setClippedEdges((previous) =>
        previous.start === start && previous.end === end ? previous : { start, end }
      );
    };
    update();
    viewport.addEventListener("scroll", update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(viewport);
    if (viewport.firstElementChild) observer.observe(viewport.firstElementChild);
    return () => {
      viewport.removeEventListener("scroll", update);
      observer.disconnect();
    };
  }, [viewportRef]);

  return clippedEdges;
}
