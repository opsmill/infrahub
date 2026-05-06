import {
  Background,
  BackgroundVariant,
  type Edge,
  MarkerType,
  type Node,
  Position,
  ReactFlow,
} from "@xyflow/react";
import dagre from "dagre";
import { exportGraph } from "infrahub-schema-visualizer";
import { type ReactNode, useCallback, useMemo, useState } from "react";
import "@xyflow/react/dist/style.css";

import { constructPath } from "@/shared/api/rest/fetch";

import type { PathTraversalResponse } from "../domain/path-traversal.types";
import { BottomToolbar, type LayoutDirection } from "./bottom-toolbar";
import { InfraNode, type InfraNodeData } from "./infra-node";
import { type EdgeStyle, PathEdge } from "./path-edge";

const nodeTypes = { infra: InfraNode };
const edgeTypes = { path: PathEdge };

const NODE_WIDTH = 180;
const NODE_HEIGHT = 65;

const PULSE_GLOW_KEYFRAMES = `@keyframes pulse-glow {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 0.5; }
}`;

function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  direction: LayoutDirection
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
  data: PathTraversalResponse | null;
  selectedPathIndex: number;
  onPathSelect?: (index: number) => void;
  onExcludeKind?: (kind: string) => void;
  parametersOpen: boolean;
  onParametersClick: () => void;
  onReload?: () => void;
  isReloading?: boolean;
  overlay?: ReactNode;
};

type ContextMenuState = {
  x: number;
  y: number;
  nodeId: string;
  nodeKind: string;
  nodeLabel: string;
} | null;

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

export function PathFlowGraph({
  data,
  selectedPathIndex,
  onExcludeKind,
  parametersOpen,
  onParametersClick,
  onReload,
  isReloading,
  overlay,
}: PathFlowGraphProps) {
  const [direction, setDirection] = useState<LayoutDirection>("LR");
  const [edgeStyle, setEdgeStyle] = useState<EdgeStyle>("bezier");
  const [contextMenu, setContextMenu] = useState<ContextMenuState>(null);

  const { nodes: flowNodes, edges: layoutedEdges } = useMemo(() => {
    if (!data?.paths.length) {
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

  const flowEdges = useMemo<Edge[]>(
    () => layoutedEdges.map((edge) => ({ ...edge, data: { ...edge.data, edgeStyle } })),
    [layoutedEdges, edgeStyle]
  );

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

  const closeContextMenu = useCallback(() => setContextMenu(null), []);
  const handleExport = useCallback(
    (format: Parameters<typeof exportGraph>[1]) => exportGraph(flowNodes, format),
    [flowNodes]
  );

  return (
    <div className="relative h-full w-full">
      <style>{PULSE_GLOW_KEYFRAMES}</style>

      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeContextMenu={onNodeContextMenu}
        onPaneClick={closeContextMenu}
        fitView
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#e5e7eb" />

        <BottomToolbar
          isParametersOpen={parametersOpen}
          onParametersClick={onParametersClick}
          edgeStyle={edgeStyle}
          onEdgeStyleChange={setEdgeStyle}
          onLayout={setDirection}
          onExport={handleExport}
          onReload={onReload}
          isReloading={isReloading}
        />
      </ReactFlow>

      {overlay && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="pointer-events-auto">{overlay}</div>
        </div>
      )}

      {contextMenu && (
        <NodeContextMenu
          menu={contextMenu}
          onClose={closeContextMenu}
          onExcludeKind={onExcludeKind}
        />
      )}
    </div>
  );
}
