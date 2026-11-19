import React from "react";

import { classNames } from "@/shared/utils/common";

import type {
  Elevation,
  ElevationItem,
  RackFace,
} from "@/entities/rack-elevation/domain/model/elevation";
import {
  canMove,
  checkPlacement,
  type Placement,
  type PlacementCheck,
} from "@/entities/rack-elevation/domain/rules/placement";
import { faceplateStyle, ghostStyle } from "@/entities/rack-elevation/ui/rack-item-style";

export interface RackElevationInteractions {
  selectedKey?: string | null;
  matchedKeys?: Set<string> | null;
  onSelectItem?: (item: ElevationItem) => void;
  onSelectUnit?: (unit: number, face: RackFace) => void;
  onSelectRack?: () => void;
  onMoveItem?: (item: ElevationItem, placement: Placement) => void;
}

interface RackElevation2DProps extends RackElevationInteractions {
  elevation: Elevation;
  unitHeight?: number;
}

interface DragState {
  item: ElevationItem;
  grabOffset: number;
}

interface DropPreview extends Placement {
  check: PlacementCheck;
}

const FACES: RackFace[] = ["front", "rear"];
const WIDTH_PER_UNIT_HEIGHT = 11;

export function RackElevation2D({
  elevation,
  unitHeight = 22,
  ...interactions
}: RackElevation2DProps) {
  const [highlightedKey, setHighlightedKey] = React.useState<string | null>(null);
  const [drag, setDrag] = React.useState<DragState | null>(null);

  return (
    <div className="flex flex-wrap items-start justify-center gap-8">
      {FACES.map((face) => (
        <RackFaceView
          key={face}
          elevation={elevation}
          face={face}
          unitHeight={unitHeight}
          highlightedKey={highlightedKey}
          onHighlight={setHighlightedKey}
          drag={drag}
          onDragChange={setDrag}
          {...interactions}
        />
      ))}
    </div>
  );
}

interface RackFaceViewProps extends RackElevationInteractions {
  elevation: Elevation;
  face: RackFace;
  unitHeight: number;
  highlightedKey: string | null;
  onHighlight: (key: string | null) => void;
  drag: DragState | null;
  onDragChange: (drag: DragState | null) => void;
}

function RackFaceView({
  elevation,
  face,
  unitHeight,
  highlightedKey,
  onHighlight,
  drag,
  onDragChange,
  selectedKey,
  matchedKeys,
  onSelectItem,
  onSelectUnit,
  onSelectRack,
  onMoveItem,
}: RackFaceViewProps) {
  const [preview, setPreview] = React.useState<DropPreview | null>(null);
  const units = Array.from({ length: elevation.height }, (_, index) => elevation.height - index);
  const width = unitHeight * WIDTH_PER_UNIT_HEIGHT;
  const isInteractive = !!onMoveItem;
  const topOf = (position: number, height: number) =>
    (elevation.height - (position + height - 1)) * unitHeight;

  const itemsOnFace = elevation.placed.filter(
    (item) => item.face === face || (item.fullDepth && item.face !== face)
  );

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    if (!drag) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const pointerUnit = elevation.height - Math.floor((event.clientY - rect.top) / unitHeight);
    const position = pointerUnit + drag.grabOffset - drag.item.height + 1;
    const placement = { position, face };
    const check = checkPlacement(elevation, drag.item, placement);
    if (check.ok) event.preventDefault();
    if (preview?.position !== position || preview.check.ok !== check.ok) {
      setPreview({ ...placement, check });
    }
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (drag && preview?.check.ok) onMoveItem?.(drag.item, preview);
    setPreview(null);
    onDragChange(null);
  };

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="font-medium text-foreground-muted text-xs uppercase tracking-wide">
        {face === "front" ? "Front" : "Rear"}
      </div>
      <div className="rounded-lg bg-stone-800 p-1 shadow-lg ring-1 ring-black/30">
        <button
          type="button"
          onClick={onSelectRack}
          disabled={!onSelectRack}
          className="mb-1 flex w-full items-center justify-between gap-2 rounded-md bg-stone-900 px-2 py-1 text-left text-stone-200 text-xs enabled:hover:bg-stone-700"
        >
          <span className="truncate font-medium">{elevation.label}</span>
          <span className="shrink-0 text-stone-400 tabular-nums">{elevation.height}U</span>
        </button>
        <div className="flex">
          <UnitRail units={units} unitHeight={unitHeight} />
          <div
            role="grid"
            aria-label={`${elevation.label} ${face}`}
            className="relative bg-stone-950"
            style={{ width, height: elevation.height * unitHeight }}
            onDragOver={handleDragOver}
            onDragLeave={() => setPreview(null)}
            onDrop={handleDrop}
          >
            {units.map((unit) => (
              <button
                key={unit}
                type="button"
                aria-label={`U${unit} ${face}`}
                disabled={!onSelectUnit}
                onClick={() => onSelectUnit?.(unit, face)}
                className="absolute inset-x-0 border-white/5 border-b enabled:hover:bg-white/10"
                style={{ top: topOf(unit, 1), height: unitHeight }}
              />
            ))}

            {itemsOnFace.map((item) => {
              const isGhost = item.face !== face;
              const isEmphasized = item.key === highlightedKey || item.key === selectedKey;
              const isMatch = matchedKeys?.has(item.key) ?? false;
              const isFilteredOut = !!matchedKeys && !isMatch;
              const isDraggable = isInteractive && !isGhost && canMove(item, face);
              const position = item.position ?? 1;
              const range =
                item.height > 1 ? `U${position}–U${position + item.height - 1}` : `U${position}`;
              return (
                <button
                  key={item.key}
                  type="button"
                  draggable={isDraggable}
                  title={`${item.label}\n${range} · ${item.height}U · ${item.face}${item.fullDepth ? " · full depth" : ""}`}
                  onClick={() => onSelectItem?.(item)}
                  onMouseEnter={() => onHighlight(item.key)}
                  onMouseLeave={() => onHighlight(null)}
                  onDragStart={(event) => {
                    const rect = event.currentTarget.getBoundingClientRect();
                    const grabOffset = Math.floor((event.clientY - rect.top) / unitHeight);
                    event.dataTransfer.effectAllowed = "move";
                    event.dataTransfer.setData("text/plain", item.key);
                    onDragChange({ item, grabOffset });
                  }}
                  onDragEnd={() => {
                    setPreview(null);
                    onDragChange(null);
                  }}
                  className={classNames(
                    "absolute inset-x-0.5 flex items-center gap-2 overflow-hidden rounded-sm border px-2 text-left text-xs transition-all",
                    isGhost ? "border-dashed text-stone-500" : "text-stone-50",
                    isDraggable && "cursor-grab active:cursor-grabbing",
                    elevation.conflicts.has(item.key) && "outline-2 outline-danger",
                    isMatch && "z-10 outline-2 outline-amber-300",
                    isFilteredOut && "opacity-20 saturate-0",
                    isEmphasized && "z-10 outline-2 outline-white/80",
                    drag?.item.key === item.key && "opacity-40"
                  )}
                  style={{
                    top: topOf(position, item.height) + 1,
                    height: item.height * unitHeight - 2,
                    ...(isGhost ? ghostStyle(item.color) : faceplateStyle(item.color)),
                  }}
                >
                  <ItemLabel item={item} isGhost={isGhost} isTall={item.height > 1} />
                </button>
              );
            })}

            {preview && drag && (
              <div
                className={classNames(
                  "pointer-events-none absolute inset-x-0.5 z-20 flex items-center justify-center rounded-sm border-2 px-2 text-center text-xs",
                  preview.check.ok
                    ? "border-emerald-400 bg-emerald-500/25 text-emerald-100"
                    : "border-red-400 bg-red-500/25 text-red-100"
                )}
                style={{
                  top: topOf(preview.position, drag.item.height),
                  height: drag.item.height * unitHeight,
                }}
              >
                <span className="truncate">
                  {preview.check.ok ? `U${preview.position}` : preview.check.reason}
                </span>
              </div>
            )}
          </div>
          <UnitRail units={units} unitHeight={unitHeight} />
        </div>
      </div>
    </div>
  );
}

function ItemLabel({
  item,
  isGhost,
  isTall,
}: {
  item: ElevationItem;
  isGhost: boolean;
  isTall: boolean;
}) {
  if (isGhost) {
    return (
      <span className="truncate">
        {item.label} · mounted {item.face}
      </span>
    );
  }
  return (
    <span
      className={classNames("flex min-w-0 flex-1", isTall ? "flex-col" : "items-baseline gap-2")}
    >
      <span className="max-w-full shrink-0 truncate font-medium">{item.label}</span>
      {item.subtitle && <span className="min-w-0 truncate text-stone-300/70">{item.subtitle}</span>}
    </span>
  );
}

function UnitRail({ units, unitHeight }: { units: number[]; unitHeight: number }) {
  return (
    <div className="w-6 bg-stone-700 text-stone-400 text-xxs tabular-nums">
      {units.map((unit) => (
        <div
          key={unit}
          className="flex items-center justify-center border-stone-800 border-b"
          style={{ height: unitHeight }}
        >
          {unit}
        </div>
      ))}
    </div>
  );
}
