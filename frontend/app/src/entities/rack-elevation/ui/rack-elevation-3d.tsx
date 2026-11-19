import { Button } from "@infrahub/ui";
import React from "react";

import { classNames } from "@/shared/utils/common";

import type { Elevation, ElevationItem } from "@/entities/rack-elevation/domain/model/elevation";
import type { RackElevationInteractions } from "@/entities/rack-elevation/ui/rack-elevation-2d";
import { RACK_FRAME_COLOR } from "@/entities/rack-elevation/ui/rack-item-style";

const UNIT = 13;
const WIDTH = UNIT * 11;
const DEPTH = WIDTH * 2;
const POST = 8;
const HALF_DEPTH_RATIO = 0.45;

interface Rotation {
  rotateX: number;
  rotateY: number;
}

const PRESETS: (Rotation & { label: string })[] = [
  { label: "Front", rotateX: -8, rotateY: 0 },
  { label: "Angle", rotateX: -16, rotateY: -35 },
  { label: "Side", rotateX: -8, rotateY: -90 },
  { label: "Rear", rotateX: -8, rotateY: 180 },
];

interface CuboidFaces {
  front?: React.ReactNode;
  back?: React.ReactNode;
}

interface CuboidProps {
  x?: number;
  y?: number;
  z?: number;
  width: number;
  height: number;
  depth: number;
  color: string;
  opacity?: number;
  faces?: CuboidFaces;
  className?: string;
  title?: string;
  onClick?: () => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
}

function shade(color: string, amount: number) {
  return `color-mix(in oklch, ${color} ${100 - amount}%, black)`;
}

function Cuboid({
  x = 0,
  y = 0,
  z = 0,
  width,
  height,
  depth,
  color,
  opacity = 1,
  faces,
  className,
  title,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: CuboidProps) {
  const face = "absolute flex items-center justify-center overflow-hidden backface-hidden";
  const edge = { border: `1px solid ${shade(color, 45)}`, opacity };

  return (
    <div
      title={title}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={classNames("transform-3d absolute top-1/2 left-1/2", className)}
      style={{
        width,
        height,
        transform: `translate3d(${x - width / 2}px, ${y - height / 2}px, ${z}px)`,
      }}
    >
      <div
        className={face}
        style={{
          ...edge,
          width,
          height,
          background: color,
          transform: `translateZ(${depth / 2}px)`,
        }}
      >
        {faces?.front}
      </div>
      <div
        className={face}
        style={{
          ...edge,
          width,
          height,
          background: shade(color, 10),
          transform: `rotateY(180deg) translateZ(${depth / 2}px)`,
        }}
      >
        {faces?.back}
      </div>
      {[90, -90].map((angle) => (
        <div
          key={angle}
          className={face}
          style={{
            ...edge,
            width: depth,
            height,
            left: (width - depth) / 2,
            background: shade(color, 30),
            transform: `rotateY(${angle}deg) translateZ(${width / 2}px)`,
          }}
        />
      ))}
      {[90, -90].map((angle) => (
        <div
          key={angle}
          className={face}
          style={{
            ...edge,
            width,
            height: depth,
            top: (height - depth) / 2,
            background: shade(color, angle > 0 ? 15 : 40),
            transform: `rotateX(${angle}deg) translateZ(${height / 2}px)`,
          }}
        />
      ))}
    </div>
  );
}

function Faceplate({ item }: { item: ElevationItem }) {
  return (
    <span className="w-full truncate px-1.5 text-left font-medium text-white text-xxs">
      {item.label}
    </span>
  );
}

function ItemCuboid({
  item,
  rackHeight,
  isEmphasized,
  isFilteredOut,
  isConflict,
  onSelect,
  onHighlight,
}: {
  item: ElevationItem;
  rackHeight: number;
  isEmphasized: boolean;
  isFilteredOut: boolean;
  isConflict: boolean;
  onSelect?: () => void;
  onHighlight: (key: string | null) => void;
}) {
  const position = item.position ?? 1;
  const height = item.height * UNIT - 1;
  const depth = item.fullDepth ? DEPTH - 2 * POST : DEPTH * HALF_DEPTH_RATIO;
  const centerY = (rackHeight * UNIT) / 2 - (position - 1) * UNIT - (item.height * UNIT) / 2;
  const offsetZ = (DEPTH - depth) / 2 - POST;
  let z = 0;
  if (!item.fullDepth) z = item.face === "front" ? offsetZ : -offsetZ;
  const color = isEmphasized ? `color-mix(in oklch, ${item.color} 70%, white)` : item.color;

  return (
    <Cuboid
      y={centerY}
      z={z}
      width={WIDTH - 2 * POST - 2}
      height={height}
      depth={depth}
      color={`color-mix(in oklch, ${color} 55%, ${RACK_FRAME_COLOR})`}
      opacity={isFilteredOut ? 0.12 : 1}
      className={classNames("cursor-pointer", isConflict && "outline-2 outline-red-500")}
      title={`${item.label} · U${position} · ${item.height}U · ${item.face}${item.fullDepth ? " · full depth" : ""}`}
      onClick={onSelect}
      onMouseEnter={() => onHighlight(item.key)}
      onMouseLeave={() => onHighlight(null)}
      faces={
        item.face === "front"
          ? { front: <Faceplate item={item} /> }
          : { back: <Faceplate item={item} /> }
      }
    />
  );
}

export function RackElevation3D({
  elevation,
  selectedKey,
  matchedKeys,
  onSelectItem,
}: { elevation: Elevation } & RackElevationInteractions) {
  const [rotation, setRotation] = React.useState<Rotation>({ rotateX: -16, rotateY: -35 });
  const [highlightedKey, setHighlightedKey] = React.useState<string | null>(null);
  const dragOrigin = React.useRef<{ x: number; y: number; rotation: Rotation } | null>(null);
  const rackPixelHeight = elevation.height * UNIT;
  const sceneHeight = rackPixelHeight + 160;
  const posts: [number, number][] = [
    [-1, 1],
    [1, 1],
    [-1, -1],
    [1, -1],
  ];

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="flex items-center gap-1">
        {PRESETS.map((preset) => (
          <Button
            key={preset.label}
            size="xs"
            variant={
              preset.rotateY === rotation.rotateY && preset.rotateX === rotation.rotateX
                ? "primary-outline"
                : "ghost"
            }
            onPress={() => setRotation(preset)}
          >
            {preset.label}
          </Button>
        ))}
        <span className="ml-2 text-foreground-muted text-xs">Drag to rotate</span>
      </div>
      <div
        className="relative w-full cursor-grab touch-none select-none overflow-hidden rounded-xl bg-content-muted active:cursor-grabbing"
        style={{ height: sceneHeight, perspective: 1800 }}
        onPointerDown={(event) => {
          if ((event.target as HTMLElement).closest("[title]")) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          dragOrigin.current = { x: event.clientX, y: event.clientY, rotation };
        }}
        onPointerMove={(event) => {
          const origin = dragOrigin.current;
          if (!origin) return;
          setRotation({
            rotateY: origin.rotation.rotateY + (event.clientX - origin.x) * 0.4,
            rotateX: Math.max(
              -60,
              Math.min(20, origin.rotation.rotateX - (event.clientY - origin.y) * 0.3)
            ),
          });
        }}
        onPointerUp={() => {
          dragOrigin.current = null;
        }}
      >
        <div
          className="transform-3d absolute inset-0"
          style={{ transform: `rotateX(${rotation.rotateX}deg) rotateY(${rotation.rotateY}deg)` }}
        >
          <div
            className="absolute top-1/2 left-1/2 rounded-full bg-black/15 blur-md"
            style={{
              width: DEPTH * 1.6,
              height: DEPTH * 1.6,
              transform: `translate(-50%, -50%) translateY(${rackPixelHeight / 2 + 2}px) rotateX(90deg)`,
            }}
          />
          {posts.map(([sx, sz]) => (
            <Cuboid
              key={`${sx}:${sz}`}
              x={(sx * (WIDTH - POST)) / 2}
              z={(sz * (DEPTH - POST)) / 2}
              width={POST}
              height={rackPixelHeight + 2 * POST}
              depth={POST}
              color="#44403c"
            />
          ))}
          {[-1, 1].map((side) => (
            <Cuboid
              key={side}
              y={side * (rackPixelHeight / 2 + POST / 2)}
              width={WIDTH}
              height={POST}
              depth={DEPTH}
              color="#292524"
            />
          ))}
          {elevation.placed.map((item) => (
            <ItemCuboid
              key={item.key}
              item={item}
              rackHeight={elevation.height}
              isEmphasized={
                item.key === highlightedKey ||
                item.key === selectedKey ||
                (matchedKeys?.has(item.key) ?? false)
              }
              isFilteredOut={!!matchedKeys && !matchedKeys.has(item.key)}
              isConflict={elevation.conflicts.has(item.key)}
              onSelect={onSelectItem ? () => onSelectItem(item) : undefined}
              onHighlight={setHighlightedKey}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
