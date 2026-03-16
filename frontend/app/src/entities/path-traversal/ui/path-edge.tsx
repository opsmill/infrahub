import { BaseEdge, EdgeLabelRenderer, type EdgeProps, getBezierPath } from "@xyflow/react";

import { formatRelName } from "./utils";

export type PathEdgeData = {
  label: string;
  highlighted?: boolean;
};

export function PathEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}: EdgeProps) {
  const edgeData = data as PathEdgeData | undefined;
  const highlighted = edgeData?.highlighted ?? true;

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      {/* Animated glow under highlighted edges */}
      {highlighted && (
        <BaseEdge
          id={`${id}-glow`}
          path={edgePath}
          style={{
            stroke: "#60a5fa",
            strokeWidth: 10,
            opacity: 0.3,
            filter: "blur(4px)",
            animation: "pulse-glow 1.5s ease-in-out infinite",
          }}
        />
      )}
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: highlighted ? "#3b82f6" : "#94a3b8",
          strokeWidth: highlighted ? 2.5 : 1,
          opacity: highlighted ? 1 : 0.6,
          strokeDasharray: highlighted ? undefined : "6 4",
        }}
      />
      {/* Only show labels on highlighted edges */}
      {highlighted && edgeData?.label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: "all",
            }}
            className="rounded border border-blue-200 bg-white px-1.5 py-0.5 text-blue-700 text-xs shadow-sm"
          >
            {formatRelName(edgeData.label)}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
