import type React from "react";
import { useRef } from "react";

import type {
  RackElevationItem,
  RackFace,
} from "@/entities/rack-elevation/domain/model/rack-elevation";

const DRAG_THRESHOLD_PX = 4;

export interface DragLocation {
  unit: number;
  face: RackFace;
}

export interface UseRackItemDragParams {
  /** Unit and face under a point of the drawing's coordinate system, or null outside the rack. */
  locate: (point: { x: number; y: number }) => DragLocation | null;
  onStartMove: (item: RackElevationItem) => void;
  onDrop: (location: DragLocation) => void;
}

interface DragState {
  item: RackElevationItem;
  startX: number;
  startY: number;
  grabbedUnit: number;
  isDragging: boolean;
}

const getSvgPoint = (event: React.PointerEvent<SVGElement>) => {
  const svg =
    event.currentTarget instanceof SVGSVGElement
      ? event.currentTarget
      : event.currentTarget.ownerSVGElement;
  const matrix = svg?.getScreenCTM();
  if (!matrix) return null;

  const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
  return { x: point.x, y: point.y };
};

export function useRackItemDrag({ locate, onStartMove, onDrop }: UseRackItemDragParams) {
  const dragRef = useRef<DragState | null>(null);
  const hasDroppedRef = useRef(false);

  const startPointer = (item: RackElevationItem, event: React.PointerEvent<SVGElement>) => {
    if (event.button !== 0 || item.position === null) return;

    const grabbed = getSvgPoint(event);
    const grabbedUnit = grabbed ? locate(grabbed)?.unit : undefined;
    if (grabbedUnit === undefined) return;

    dragRef.current = {
      item,
      startX: event.clientX,
      startY: event.clientY,
      grabbedUnit,
      isDragging: false,
    };
  };

  const movePointer = (event: React.PointerEvent<SVGElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.isDragging) return;

    const distance = Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY);
    if (distance < DRAG_THRESHOLD_PX) return;

    drag.isDragging = true;
    onStartMove(drag.item);
  };

  const endPointer = (event: React.PointerEvent<SVGElement>) => {
    const drag = dragRef.current;
    dragRef.current = null;
    if (!drag?.isDragging || drag.item.position === null) return;

    hasDroppedRef.current = true;
    const point = getSvgPoint(event);
    const location = point ? locate(point) : null;
    if (!location) return;

    // The item keeps the offset between its lowest unit and the unit that was grabbed.
    onDrop({ ...location, unit: location.unit - (drag.grabbedUnit - drag.item.position) });
  };

  const cancelPointer = () => {
    dragRef.current = null;
  };

  /** True once for the click that follows a drop, so the drop does not also open the item. */
  const consumeDropClick = () => {
    const hasDropped = hasDroppedRef.current;
    hasDroppedRef.current = false;
    return hasDropped;
  };

  return { startPointer, movePointer, endPointer, cancelPointer, consumeDropClick };
}
