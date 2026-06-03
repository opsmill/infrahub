import {
  BaseEdge,
  EdgeLabelRenderer,
  type EdgeProps,
  getBezierPath,
  getSmoothStepPath,
} from "@xyflow/react";

export type EdgeStyle = "bezier" | "smoothstep";

export type PathEdgeData = {
  label: string;
  highlighted?: boolean;
  edgeStyle?: EdgeStyle;
};

const HIGHLIGHTED_GLOW_STYLE: React.CSSProperties = {
  stroke: "#60a5fa",
  strokeWidth: 10,
  opacity: 0.3,
  filter: "blur(4px)",
  animation: "pulse-glow 1.5s ease-in-out infinite",
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
  const edgeStyle = edgeData?.edgeStyle ?? "bezier";

  const pathArgs = { sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition };
  const [edgePath, labelX, labelY] =
    edgeStyle === "smoothstep" ? getSmoothStepPath(pathArgs) : getBezierPath(pathArgs);

  const baseStyle: React.CSSProperties = {
    stroke: highlighted ? "#3b82f6" : "#94a3b8",
    strokeWidth: highlighted ? 2.5 : 1,
    opacity: highlighted ? 1 : 0.6,
    strokeDasharray: highlighted ? undefined : "6 4",
  };

  return (
    <>
      {highlighted && <BaseEdge id={`${id}-glow`} path={edgePath} style={HIGHLIGHTED_GLOW_STYLE} />}
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={baseStyle} />
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
            {edgeData.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
