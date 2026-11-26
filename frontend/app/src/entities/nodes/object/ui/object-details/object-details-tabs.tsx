import { Button, ScrollArea } from "@infrahub/ui";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import { type RefObject, useEffect, useRef, useState } from "react";

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

  const viewportRef = useRef<HTMLDivElement>(null);
  const { canScrollLeft, canScrollRight } = useHorizontalOverflow(viewportRef);

  const scrollTabs = (direction: -1 | 1) => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    viewport.scrollBy({ left: direction * viewport.clientWidth * 0.8, behavior: "smooth" });
  };

  return (
    <div className="relative shrink-0">
      <ScrollArea
        ref={viewportRef}
        type="auto"
        scrollX
        scrollY={false}
        // A mask fades the tabs into whatever surface is behind them, so the fade fits
        // the light and dark card gradients alike.
        style={{ maskImage: getEdgeFadeMask(canScrollLeft, canScrollRight) }}
      >
        <nav aria-label="Tabs" className="pb-1">
          <Row className="items-end gap-4 px-4" data-testid="object-details-tabs">
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
            {isRepository && (
              <RepositoryCommitsTab
                objectKind={objectKind}
                objectId={objectId}
                internalStatus={getRepositoryInternalStatus(objectData)}
              />
            )}
          </Row>
        </nav>
      </ScrollArea>
      {canScrollLeft && (
        <div className="absolute top-0 bottom-1 left-1 flex items-center">
          <Button
            variant="outline"
            size="xs"
            shape="circle"
            aria-label="Scroll tabs left"
            onPress={() => scrollTabs(-1)}
          >
            <ChevronLeftIcon />
          </Button>
        </div>
      )}
      {canScrollRight && (
        <div className="absolute top-0 right-1 bottom-1 flex items-center">
          <Button
            variant="outline"
            size="xs"
            shape="circle"
            aria-label="Scroll tabs right"
            onPress={() => scrollTabs(1)}
          >
            <ChevronRightIcon />
          </Button>
        </div>
      )}
    </div>
  );
}

const EDGE_FADE = "4rem";

function getEdgeFadeMask(fadeLeft: boolean, fadeRight: boolean): string | undefined {
  if (!(fadeLeft || fadeRight)) return undefined;
  const start = fadeLeft ? `transparent, black ${EDGE_FADE}` : "black";
  const end = fadeRight ? `black calc(100% - ${EDGE_FADE}), transparent` : "black";
  return `linear-gradient(to right, ${start}, ${end})`;
}

// Tracks which sides of a horizontal scroll container hide content, and lets a vertical
// mouse wheel scroll it sideways, since most mice cannot scroll horizontally.
function useHorizontalOverflow(viewportRef: RefObject<HTMLDivElement | null>) {
  const [overflow, setOverflow] = useState({ canScrollLeft: false, canScrollRight: false });

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    const update = () => {
      const maxScrollLeft = viewport.scrollWidth - viewport.clientWidth;
      setOverflow({
        canScrollLeft: viewport.scrollLeft > 1,
        canScrollRight: viewport.scrollLeft < maxScrollLeft - 1,
      });
    };

    const onWheel = (event: WheelEvent) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
      const maxScrollLeft = viewport.scrollWidth - viewport.clientWidth;
      const atEdge =
        (event.deltaY < 0 && viewport.scrollLeft <= 0) ||
        (event.deltaY > 0 && viewport.scrollLeft >= maxScrollLeft - 1);
      // Hand the wheel back to the page when the tabs fit or are already at that edge.
      if (maxScrollLeft <= 0 || atEdge) return;
      event.preventDefault();
      viewport.scrollLeft += event.deltaY;
    };

    update();
    viewport.addEventListener("scroll", update, { passive: true });
    viewport.addEventListener("wheel", onWheel, { passive: false });
    const resizeObserver = new ResizeObserver(update);
    resizeObserver.observe(viewport);
    if (viewport.firstElementChild) resizeObserver.observe(viewport.firstElementChild);

    return () => {
      viewport.removeEventListener("scroll", update);
      viewport.removeEventListener("wheel", onWheel);
      resizeObserver.disconnect();
    };
  }, [viewportRef]);

  return overflow;
}
