import {
  Background,
  BackgroundVariant,
  type Edge,
  MarkerType,
  type Node,
  Position,
  ReactFlow,
  useReactFlow,
} from "@xyflow/react";
import dagre from "dagre";
import { useCallback, useMemo, useState } from "react";
import "@xyflow/react/dist/style.css";

import { constructPath } from "@/shared/api/rest/fetch";

import type { PathTraversalResponse } from "../domain/get-path-traversal";
import { InfraNode, type InfraNodeData } from "./infra-node";
import { PathEdge } from "./path-edge";

const nodeTypes = { infra: InfraNode };
const edgeTypes = { path: PathEdge };

const NODE_WIDTH = 180;
const NODE_HEIGHT = 65;

function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  direction: "LR" | "TB" = "LR"
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 80, ranksep: 140 });

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      },
      sourcePosition: direction === "TB" ? Position.Bottom : Position.Right,
      targetPosition: direction === "TB" ? Position.Top : Position.Left,
    };
  });

  return { nodes: layoutedNodes, edges };
}

type PathFlowGraphProps = {
  data: PathTraversalResponse;
  selectedPathIndex: number;
  onPathSelect?: (index: number) => void;
  onExcludeKind?: (kind: string) => void;
};

type ContextMenuState = {
  x: number;
  y: number;
  nodeId: string;
  nodeKind: string;
  nodeLabel: string;
} | null;

function FitViewButton() {
  const reactFlowInstance = useReactFlow();
  return (
    <button
      type="button"
      onClick={() => reactFlowInstance.fitView()}
      className="rounded border border-gray-200 bg-white p-1.5 shadow-sm hover:bg-gray-50"
      title="Fit view"
    >
      <svg
        className="size-4 text-gray-600"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5"
        />
      </svg>
    </button>
  );
}

function NodeContextMenu({
  menu,
  onClose,
  onExcludeKind,
}: {
  menu: NonNullable<ContextMenuState>;
  onClose: () => void;
  onExcludeKind?: (kind: string) => void;
}) {
  function handleCopyId() {
    navigator.clipboard.writeText(menu.nodeId);
    onClose();
  }

  const detailsUrl = constructPath(`/objects/${menu.nodeKind}/${menu.nodeId}`);
  const pathAsSourceUrl = constructPath("/path-traversal", [
    { name: "source", value: menu.nodeId },
  ]);
  const pathAsDestUrl = constructPath("/path-traversal", [
    { name: "destination", value: menu.nodeId },
  ]);

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div
        className="fixed z-50 min-w-[180px] rounded-md border border-gray-200 bg-white py-1 shadow-lg"
        style={{ left: menu.x, top: menu.y }}
      >
        <div className="border-gray-100 border-b px-3 py-1.5">
          <div className="truncate font-medium text-xs">{menu.nodeLabel}</div>
          <div className="truncate text-[10px] text-gray-400">{menu.nodeKind}</div>
        </div>
        <a
          href={detailsUrl}
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-gray-50"
          onClick={onClose}
        >
          Open details
        </a>
        <a
          href={pathAsSourceUrl}
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-gray-50"
          onClick={onClose}
        >
          Set as source
        </a>
        <a
          href={pathAsDestUrl}
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-gray-50"
          onClick={onClose}
        >
          Set as destination
        </a>
        <button
          type="button"
          onClick={handleCopyId}
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-gray-50"
        >
          Copy ID
        </button>
        {onExcludeKind && (
          <>
            <div className="mx-2 my-0.5 border-gray-100 border-t" />
            <button
              type="button"
              onClick={() => {
                onExcludeKind(menu.nodeKind);
                onClose();
              }}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-red-600 text-xs hover:bg-red-50"
            >
              Exclude {menu.nodeKind}
            </button>
          </>
        )}
      </div>
    </>
  );
}

export function PathFlowGraph({ data, selectedPathIndex, onExcludeKind }: PathFlowGraphProps) {
  const [direction, setDirection] = useState<"LR" | "TB">("LR");
  const [contextMenu, setContextMenu] = useState<ContextMenuState>(null);

  const { nodes: flowNodes, edges: flowEdges } = useMemo(() => {
    if (!data.paths.length) {
      return { nodes: [] as Node[], edges: [] as Edge[] };
    }

    const nodeMap = new Map<string, InfraNodeData & { id: string }>();
    const edgeSet = new Set<string>();
    const edges: Edge[] = [];

    const selectedPath = data.paths[selectedPathIndex];
    const selectedObjectIds = new Set(selectedPath?.objects.map((o) => o.id) ?? []);
    const selectedEdgeKeys = new Set<string>();

    if (selectedPath) {
      for (let i = 0; i < selectedPath.objects.length - 1; i++) {
        const currentObject = selectedPath.objects[i];
        const nextObject = selectedPath.objects[i + 1];
        if (currentObject && nextObject) {
          selectedEdgeKeys.add(`${currentObject.id}-${nextObject.id}`);
          selectedEdgeKeys.add(`${nextObject.id}-${currentObject.id}`);
        }
      }
    }

    for (const path of data.paths) {
      for (const object of path.objects) {
        if (!nodeMap.has(object.id)) {
          nodeMap.set(object.id, {
            id: object.id,
            label: object.display_label,
            kind: object.kind,
            nodeId: object.id,
            isSource: object.id === data.source.id,
            isDestination: object.id === data.destination.id,
            highlighted: selectedObjectIds.has(object.id),
          });
        }
      }

      for (let i = 0; i < path.objects.length - 1; i++) {
        const sourceObject = path.objects[i];
        const targetObject = path.objects[i + 1];
        if (!sourceObject || !targetObject) continue;
        const sourceId = sourceObject.id;
        const targetId = targetObject.id;
        const edgeKey = `${sourceId}-${targetId}`;

        if (!edgeSet.has(edgeKey)) {
          edgeSet.add(edgeKey);
          const relName = path.relationships[i]?.name ?? "";
          const isHighlighted = selectedEdgeKeys.has(edgeKey);

          edges.push({
            id: edgeKey,
            source: sourceId,
            target: targetId,
            type: "path",
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: isHighlighted ? "#3b82f6" : "#d1d5db",
            },
            data: { label: relName, highlighted: isHighlighted },
          });
        }
      }
    }

    const nodes: Node[] = Array.from(nodeMap.values()).map((n) => ({
      id: n.id,
      type: "infra",
      position: { x: 0, y: 0 },
      data: {
        label: n.label,
        kind: n.kind,
        nodeId: n.id,
        isSource: n.isSource,
        isDestination: n.isDestination,
        highlighted: n.highlighted,
        direction,
      },
    }));

    return getLayoutedElements(nodes, edges, direction);
  }, [data, selectedPathIndex, direction]);

  const onInit = useCallback((instance: { fitView: () => void }) => {
    instance.fitView();
  }, []);

  const onNodeContextMenu = useCallback((event: React.MouseEvent, node: Node) => {
    event.preventDefault();
    const nodeData = node.data as InfraNodeData;
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      nodeId: nodeData.nodeId,
      nodeKind: nodeData.kind,
      nodeLabel: nodeData.label,
    });
  }, []);

  if (!data.paths.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-gray-400">
        <svg
          className="size-12"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.07-9.07a4.5 4.5 0 00-6.364 0l-4.5 4.5a4.5 4.5 0 001.242 7.244"
          />
        </svg>
        <span>No paths found between these nodes.</span>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      {/* Glow animation CSS */}
      <style>
        {`@keyframes pulse-glow {
          0%, 100% { opacity: 0.2; }
          50% { opacity: 0.5; }
        }`}
      </style>

      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onInit={onInit}
        onNodeContextMenu={onNodeContextMenu}
        onPaneClick={() => setContextMenu(null)}
        fitView
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <div className="absolute top-2 right-2 z-10 flex gap-1">
          <button
            type="button"
            onClick={() => setDirection((d) => (d === "LR" ? "TB" : "LR"))}
            className="rounded border border-gray-200 bg-white p-1.5 shadow-sm hover:bg-gray-50"
            title={`Switch to ${direction === "LR" ? "top-bottom" : "left-right"} layout`}
          >
            <svg
              className="size-4 text-gray-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              {direction === "LR" ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m-6-6l6 6 6-6" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 12h16m-6-6l6 6-6 6" />
              )}
            </svg>
          </button>
          <FitViewButton />
        </div>
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#e5e7eb" />
      </ReactFlow>

      {contextMenu && (
        <NodeContextMenu
          menu={contextMenu}
          onClose={() => setContextMenu(null)}
          onExcludeKind={onExcludeKind}
        />
      )}
    </div>
  );
}
