import { ScrollArea } from "@infrahub/ui";
import {
  type CSSProperties,
  type ReactNode,
  type RefObject,
  useEffect,
  useRef,
  useState,
} from "react";

import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

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

const EDGE_FADE = "48px";

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

// The last tab sits outside the scroll area so its signal is never scrolled away; a mask, not a colour, fades the cut edge because the card background is a gradient.
function TabsWithPinnedLastTab({ children, lastTab }: { children: ReactNode; lastTab: ReactNode }) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const cutEdges = useCutEdges(viewportRef);

  return (
    <nav aria-label="Tabs" className="shrink-0">
      <Row className="items-end gap-0" data-testid="object-details-tabs">
        <ScrollArea
          ref={viewportRef}
          scrollX
          scrollY={false}
          scrollBarClassName="hidden"
          className="min-w-0 shrink"
          style={getEdgeMask(cutEdges)}
        >
          <Row className="items-end gap-4 pl-4">{children}</Row>
        </ScrollArea>
        <div className="flex shrink-0 px-4" data-testid="object-details-pinned-tab">
          {lastTab}
        </div>
      </Row>
    </nav>
  );
}

interface CutEdges {
  start: boolean;
  end: boolean;
}

function useCutEdges(viewportRef: RefObject<HTMLDivElement | null>): CutEdges {
  const [cutEdges, setCutEdges] = useState<CutEdges>({ start: false, end: false });

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    const update = () => {
      const start = viewport.scrollLeft > 1;
      const end = viewport.scrollWidth - viewport.clientWidth - viewport.scrollLeft > 1;
      setCutEdges((previous) =>
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

  return cutEdges;
}

function getEdgeMask({ start, end }: CutEdges): CSSProperties | undefined {
  if (!start && !end) return undefined;
  const from = start ? `transparent, black ${EDGE_FADE}` : "black";
  const to = end ? `black calc(100% - ${EDGE_FADE}), transparent` : "black";
  const mask = `linear-gradient(to right, ${from}, ${to})`;
  return { maskImage: mask, WebkitMaskImage: mask };
}
