import { Handle, type NodeProps, Position } from "@xyflow/react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";

import { getKindColor } from "./utils";

export type InfraNodeData = {
  label: string;
  kind: string;
  nodeId: string;
  isSource?: boolean;
  isDestination?: boolean;
  highlighted?: boolean;
  direction?: "LR" | "TB";
};

export function InfraNode({ data }: NodeProps) {
  const nodeData = data as InfraNodeData;
  const isSource = nodeData.isSource;
  const isDestination = nodeData.isDestination;
  const direction = nodeData.direction ?? "LR";
  const navigate = useNavigate();
  const [showTooltip, setShowTooltip] = useState(false);

  const targetPosition = direction === "TB" ? Position.Top : Position.Left;
  const sourcePosition = direction === "TB" ? Position.Bottom : Position.Right;

  function handleClick() {
    const url = getObjectDetailsUrl(nodeData.kind, nodeData.nodeId);
    navigate(url);
  }

  let borderColor = "border-gray-300";
  let bgColor = "bg-white";
  const showKindStripe = !isSource && !isDestination && !nodeData.highlighted;
  const kindColor = getKindColor(nodeData.kind);

  if (isSource) {
    borderColor = "border-emerald-500";
    bgColor = "bg-emerald-50";
  } else if (isDestination) {
    borderColor = "border-orange-500";
    bgColor = "bg-orange-50";
  } else if (nodeData.highlighted) {
    borderColor = "border-blue-400";
    bgColor = "bg-blue-50";
  }

  const dimmed = !nodeData.highlighted && !isSource && !isDestination;

  return (
    <div
      className={`relative min-w-[150px] max-w-[220px] cursor-pointer rounded-lg border-2 px-3 py-2 text-center shadow-sm transition-all hover:shadow-md ${borderColor} ${bgColor}
        ${dimmed ? "opacity-40" : ""}
      `}
      onClick={handleClick}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {showKindStripe && (
        <div
          className="absolute top-0 left-0 h-full w-1 rounded-l-lg"
          style={{ backgroundColor: kindColor }}
        />
      )}
      <Handle type="target" position={targetPosition} className="!bg-gray-400" />

      {/* Endpoint badge */}
      {isSource && (
        <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-2 py-0.5 font-bold text-[10px] text-white leading-none">
          SOURCE
        </div>
      )}
      {isDestination && (
        <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 rounded-full bg-orange-500 px-2 py-0.5 font-bold text-[10px] text-white leading-none">
          DEST
        </div>
      )}

      <div className="mt-1 truncate font-medium text-sm">{nodeData.label}</div>
      <div className="truncate text-[11px] text-gray-500">{nodeData.kind}</div>

      <Handle type="source" position={sourcePosition} className="!bg-gray-400" />

      {showTooltip && (
        <div className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md border border-gray-200 bg-white px-3 py-2 text-left shadow-lg">
          <div className="font-medium text-sm">{nodeData.label}</div>
          <div className="text-gray-500 text-xs">{nodeData.kind}</div>
          <div className="mt-1 font-mono text-[10px] text-gray-400">{nodeData.nodeId}</div>
          <div className="mt-1 text-[10px] text-blue-500">Click to open details</div>
        </div>
      )}
    </div>
  );
}
