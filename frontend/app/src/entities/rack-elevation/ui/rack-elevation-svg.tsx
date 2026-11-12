import type React from "react";

import {
  RACK_FACES,
  type RackElevation,
  type RackElevationItem,
  type RackFace,
  RackItemPlacement,
} from "@/entities/rack-elevation/domain/model/rack-elevation";
import {
  getFreeUnits,
  getPlacementTargets,
} from "@/entities/rack-elevation/domain/rules/get-free-units";
import { getUnitFromPointer } from "@/entities/rack-elevation/domain/rules/get-unit-from-pointer";
import { truncateLabel } from "@/entities/rack-elevation/domain/rules/truncate-label";
import {
  type DragLocation,
  useRackItemDrag,
} from "@/entities/rack-elevation/ui/hooks/use-rack-item-drag";

const UNIT_HEIGHT = 24;
const COLUMN_WIDTH = 220;
const GUTTER_WIDTH = 28;
const COLUMN_GAP = 16;
const PADDING = 8;
const HEADER_HEIGHT = 32;
const FOOTER_HEIGHT = 36;
const FONT_SIZE = 12;
const CHARACTER_WIDTH = 7;
const LABEL_INSET = 8;
const MOVE_HANDLE_SIZE = 18;
const DIMMED_OPACITY = 0.35;

const NEUTRAL_ITEM_COLOR = "#9ca3af";
const FRAME_COLOR = "#374151";
const GRID_COLOR = "#e5e7eb";
const TEXT_COLOR = "#111827";
const MUTED_TEXT_COLOR = "#6b7280";
const ACCENT_COLOR = "#2563eb";
const HATCH_PATTERN_ID = "rack-elevation-hatch";

const COLUMN_STRIDE = COLUMN_WIDTH + 2 * GUTTER_WIDTH + COLUMN_GAP;
const DRAWING_WIDTH = 2 * PADDING + 2 * COLUMN_STRIDE - COLUMN_GAP;
const MAX_LABEL_CHARACTERS = Math.floor(
  (COLUMN_WIDTH - LABEL_INSET - MOVE_HANDLE_SIZE) / CHARACTER_WIDTH
);

const FACE_LABELS: Record<RackFace, string> = { FRONT: "Front", REAR: "Rear" };

const DRAWING_STYLES = `
  .rack-free-unit { fill: transparent; cursor: pointer; outline: none; }
  .rack-free-unit:hover, .rack-free-unit:focus-visible { fill: rgba(37, 99, 235, 0.18); }
  .rack-unit-hint { fill: rgba(37, 99, 235, 0.25); }
  .rack-item { cursor: pointer; outline: none; }
  .rack-item:focus-visible > rect:first-of-type { stroke: ${ACCENT_COLOR}; stroke-width: 2; }
  .rack-item-move { opacity: 0; cursor: pointer; outline: none; }
  .rack-item:hover .rack-item-move, .rack-item-move:focus-visible { opacity: 1; }
`;

const getColumnLeft = (face: RackFace) =>
  PADDING + RACK_FACES.indexOf(face) * COLUMN_STRIDE + GUTTER_WIDTH;
const getUnitTop = (unit: number, uHeight: number) =>
  HEADER_HEIGHT + (uHeight - unit) * UNIT_HEIGHT;
const getFaceKey = (face: RackFace) => face.toLowerCase();

const locateUnit = ({
  x,
  y,
  uHeight,
}: {
  x: number;
  y: number;
  uHeight: number;
}): DragLocation | null => {
  const unit = getUnitFromPointer({
    y,
    top: HEADER_HEIGHT,
    unitHeight: UNIT_HEIGHT,
    rackHeight: uHeight,
  });
  const face = RACK_FACES.find(
    (candidate) => x >= getColumnLeft(candidate) && x < getColumnLeft(candidate) + COLUMN_WIDTH
  );

  return unit === null || face === undefined ? null : { unit, face };
};

const isActivationKey = (event: React.KeyboardEvent) => event.key === "Enter" || event.key === " ";

export interface UnitTarget {
  unit: number;
  face: RackFace;
}

export interface RackElevationSvgProps {
  elevation: RackElevation;
  footerText: string;
  movingItemId: string | null;
  onOpenItem: (item: RackElevationItem) => void;
  onStartMove: (item: RackElevationItem) => void;
  onSelectUnit: (target: UnitTarget) => void;
  ref?: React.Ref<SVGSVGElement>;
}

export function RackElevationSvg({
  elevation,
  footerText,
  movingItemId,
  onOpenItem,
  onStartMove,
  onSelectUnit,
  ref,
}: RackElevationSvgProps) {
  const { rack, items } = elevation;
  const movingItem = items.find((item) => item.id === movingItemId) ?? null;
  const mountedItems = items.filter(
    (item) =>
      item.placement === RackItemPlacement.MOUNTED && item.position !== null && item.face !== null
  );
  const freeUnits = getFreeUnits({ items, uHeight: rack.u_height });
  const targets = movingItem
    ? getPlacementTargets({ items, uHeight: rack.u_height, movingItem })
    : null;
  const units = Array.from({ length: rack.u_height }, (_, index) => index + 1);
  const height = HEADER_HEIGHT + rack.u_height * UNIT_HEIGHT + FOOTER_HEIGHT;
  const rowsBottom = HEADER_HEIGHT + rack.u_height * UNIT_HEIGHT;

  const drag = useRackItemDrag({
    locate: ({ x, y }) => locateUnit({ x, y, uHeight: rack.u_height }),
    onStartMove,
    onDrop: onSelectUnit,
  });

  const isFree = (face: RackFace, unit: number) =>
    freeUnits[face].some((range) => unit >= range.start && unit <= range.end);

  return (
    <svg
      ref={ref}
      xmlns="http://www.w3.org/2000/svg"
      width={DRAWING_WIDTH}
      height={height}
      viewBox={`0 0 ${DRAWING_WIDTH} ${height}`}
      fontFamily="system-ui, sans-serif"
      fontSize={FONT_SIZE}
      role="img"
      aria-label={`Elevation of ${rack.display_label}`}
      data-testid="rack-elevation-svg"
      onPointerMove={drag.movePointer}
      onPointerUp={drag.endPointer}
      onPointerLeave={drag.cancelPointer}
    >
      <style>{DRAWING_STYLES}</style>
      <defs>
        <pattern
          id={HATCH_PATTERN_ID}
          width="6"
          height="6"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <line x1="0" y1="0" x2="0" y2="6" stroke={FRAME_COLOR} strokeWidth="2" />
        </pattern>
      </defs>
      <rect width={DRAWING_WIDTH} height={height} fill="#ffffff" />

      {RACK_FACES.map((face) => {
        const left = getColumnLeft(face);
        return (
          <g key={face} data-face={getFaceKey(face)}>
            <text
              x={left + COLUMN_WIDTH / 2}
              y={HEADER_HEIGHT / 2 + FONT_SIZE / 2 - 2}
              textAnchor="middle"
              fontWeight="600"
              fill={TEXT_COLOR}
            >
              {FACE_LABELS[face]}
            </text>
            {units.map((unit) => {
              const top = getUnitTop(unit, rack.u_height);
              const numberY = top + UNIT_HEIGHT / 2 + FONT_SIZE / 2 - 2;
              return (
                <g key={unit}>
                  <rect
                    x={left}
                    y={top}
                    width={COLUMN_WIDTH}
                    height={UNIT_HEIGHT}
                    fill="#f9fafb"
                    stroke={GRID_COLOR}
                  />
                  <text
                    x={left - GUTTER_WIDTH / 2}
                    y={numberY}
                    textAnchor="middle"
                    fill={MUTED_TEXT_COLOR}
                  >
                    {unit}
                  </text>
                  <text
                    x={left + COLUMN_WIDTH + GUTTER_WIDTH / 2}
                    y={numberY}
                    textAnchor="middle"
                    fill={MUTED_TEXT_COLOR}
                  >
                    {unit}
                  </text>
                </g>
              );
            })}
            <rect
              x={left}
              y={HEADER_HEIGHT}
              width={COLUMN_WIDTH}
              height={rack.u_height * UNIT_HEIGHT}
              fill="none"
              stroke={FRAME_COLOR}
              strokeWidth="2"
            />
          </g>
        );
      })}

      {mountedItems.map((item) =>
        RACK_FACES.filter((face) => face === item.face || item.full_depth).map((face) => (
          <RackItemShape
            key={`${item.id}-${face}`}
            item={item}
            face={face}
            uHeight={rack.u_height}
            isDimmed={face !== item.face}
            isMoving={item.id === movingItemId}
            isMoveMode={movingItem !== null}
            onOpenItem={onOpenItem}
            onStartMove={onStartMove}
            drag={drag}
          />
        ))
      )}

      {RACK_FACES.flatMap((face) =>
        units
          .filter((unit) => movingItem !== null || isFree(face, unit))
          .map((unit) => (
            <rect
              key={`${face}-${unit}`}
              x={getColumnLeft(face)}
              y={getUnitTop(unit, rack.u_height)}
              width={COLUMN_WIDTH}
              height={UNIT_HEIGHT}
              className={
                targets?.[face].has(unit) ? "rack-free-unit rack-unit-hint" : "rack-free-unit"
              }
              data-testid={`rack-unit-${getFaceKey(face)}-${unit}`}
              data-export-hidden="true"
              role="button"
              tabIndex={0}
              aria-label={`Place at unit ${unit} ${getFaceKey(face)}`}
              onClick={() => onSelectUnit({ unit, face })}
              onKeyDown={(event) => {
                if (!isActivationKey(event)) return;
                event.preventDefault();
                onSelectUnit({ unit, face });
              }}
            />
          ))
      )}

      <text
        x={PADDING}
        y={rowsBottom + FOOTER_HEIGHT / 2 + 2}
        fontSize="11"
        fill={MUTED_TEXT_COLOR}
      >
        {footerText}
      </text>
    </svg>
  );
}

interface RackItemShapeProps {
  item: RackElevationItem;
  face: RackFace;
  uHeight: number;
  isDimmed: boolean;
  isMoving: boolean;
  isMoveMode: boolean;
  onOpenItem: (item: RackElevationItem) => void;
  onStartMove: (item: RackElevationItem) => void;
  drag: ReturnType<typeof useRackItemDrag>;
}

function RackItemShape({
  item,
  face,
  uHeight,
  isDimmed,
  isMoving,
  isMoveMode,
  onOpenItem,
  onStartMove,
  drag,
}: RackItemShapeProps) {
  const position = item.position ?? 1;
  const left = getColumnLeft(face);
  const top = getUnitTop(position + item.u_height - 1, uHeight);
  const height = item.u_height * UNIT_HEIGHT;
  const fill = item.color ?? NEUTRAL_ITEM_COLOR;
  const typeText = item.type_display_label ?? "No type";

  const open = () => {
    if (drag.consumeDropClick()) return;
    if (!isMoveMode) onOpenItem(item);
  };

  return (
    <g
      className="rack-item"
      data-testid={`rack-item-${item.display_label}`}
      data-item-id={item.id}
      data-position={position}
      data-face={getFaceKey(face)}
      data-dimmed={isDimmed ? "true" : undefined}
      role="link"
      tabIndex={0}
      aria-label={`${item.label}, ${typeText}${isDimmed ? ", mounted on the other face" : ""}`}
      onClick={open}
      onPointerDown={isDimmed ? undefined : (event) => drag.startPointer(item, event)}
      onKeyDown={(event) => {
        if (!isActivationKey(event)) return;
        event.preventDefault();
        open();
      }}
    >
      <title>{`${item.label} · ${typeText}`}</title>
      <rect
        x={left}
        y={top}
        width={COLUMN_WIDTH}
        height={height}
        fill={fill}
        fillOpacity={isDimmed ? DIMMED_OPACITY : 1}
        stroke={isMoving ? ACCENT_COLOR : FRAME_COLOR}
        strokeWidth={isMoving ? 3 : 1}
        strokeDasharray={isMoving ? "6 3" : undefined}
      />
      {isDimmed && (
        <rect
          x={left}
          y={top}
          width={COLUMN_WIDTH}
          height={height}
          fill={`url(#${HATCH_PATTERN_ID})`}
          fillOpacity={0.25}
          pointerEvents="none"
        />
      )}
      <text
        x={left + LABEL_INSET}
        y={top + UNIT_HEIGHT / 2 + FONT_SIZE / 2 - 2}
        fill={TEXT_COLOR}
        fillOpacity={isDimmed ? 0.6 : 1}
        pointerEvents="none"
      >
        {truncateLabel(item.label, MAX_LABEL_CHARACTERS)}
      </text>
      {!isDimmed && (
        <g
          className="rack-item-move"
          data-testid={`rack-item-move-${item.display_label}`}
          data-export-hidden="true"
          role="button"
          tabIndex={0}
          aria-label={`Move ${item.label}`}
          onPointerDown={(event) => event.stopPropagation()}
          onClick={(event) => {
            event.stopPropagation();
            onStartMove(item);
          }}
          onKeyDown={(event) => {
            if (!isActivationKey(event)) return;
            event.preventDefault();
            event.stopPropagation();
            onStartMove(item);
          }}
        >
          <title>Move</title>
          <rect
            x={left + COLUMN_WIDTH - MOVE_HANDLE_SIZE - 3}
            y={top + 3}
            width={MOVE_HANDLE_SIZE}
            height={UNIT_HEIGHT - 6}
            rx="3"
            fill="#ffffff"
            stroke={FRAME_COLOR}
          />
          <text
            x={left + COLUMN_WIDTH - MOVE_HANDLE_SIZE / 2 - 3}
            y={top + UNIT_HEIGHT / 2 + FONT_SIZE / 2 - 2}
            textAnchor="middle"
            fill={TEXT_COLOR}
            pointerEvents="none"
          >
            ⇅
          </text>
        </g>
      )}
    </g>
  );
}
