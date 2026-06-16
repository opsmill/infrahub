import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import { useReactFlow } from "@xyflow/react";

import { Toolbar } from "../toolbar/toolbar";

export type EdgeStyle = "bezier" | "smoothstep";
export type LayoutDirection = "TB" | "LR";

export interface GraphControlsProps {
  edgeStyle: EdgeStyle;
  onEdgeStyleChange: (style: EdgeStyle) => void;
  onLayout: (direction: LayoutDirection) => void;
}

/** The common graph-canvas controls shared by graph views: zoom out / fit / zoom in,
 *  an edge-style toggle, and auto-layout (horizontal / vertical). Reads the ReactFlow
 *  instance from context for zoom/fit. Render inside a `Toolbar`; compose feature-specific
 *  buttons (filters, reload, export, …) alongside it. */
export function GraphControls({ edgeStyle, onEdgeStyleChange, onLayout }: GraphControlsProps) {
  const { zoomIn, zoomOut, fitView } = useReactFlow();

  return (
    <>
      <Tooltip message="Zoom out">
        <Button
          variant="ghost"
          size="sm"
          shape="square"
          aria-label="Zoom out"
          onPress={() => zoomOut()}
          className="text-gray-600"
        >
          <Icon icon="mdi:minus" className="text-lg" />
        </Button>
      </Tooltip>
      <Tooltip message="Fit to screen">
        <Button
          variant="ghost"
          size="sm"
          shape="square"
          aria-label="Fit to screen"
          onPress={() => fitView({ padding: 0.2 })}
          className="text-gray-600"
        >
          <Icon icon="mdi:fit-to-screen" className="text-lg" />
        </Button>
      </Tooltip>
      <Tooltip message="Zoom in">
        <Button
          variant="ghost"
          size="sm"
          shape="square"
          aria-label="Zoom in"
          onPress={() => zoomIn()}
          className="text-gray-600"
        >
          <Icon icon="mdi:plus" className="text-lg" />
        </Button>
      </Tooltip>
      <Toolbar.Divider className="mx-2" />
      <Tooltip message={`Switch to ${edgeStyle === "bezier" ? "step" : "smooth"} edges`}>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Toggle edge style"
          onPress={() => onEdgeStyleChange(edgeStyle === "bezier" ? "smoothstep" : "bezier")}
          className="text-gray-600"
        >
          <Icon
            icon={edgeStyle === "bezier" ? "mdi:vector-curve" : "mdi:vector-polyline"}
            className="text-lg"
          />
          <span className="text-xs">{edgeStyle === "bezier" ? "Smooth" : "Step"}</span>
        </Button>
      </Tooltip>
      <Toolbar.Divider className="mx-2" />
      <Tooltip message="Auto-layout horizontal">
        <Button
          variant="ghost"
          size="sm"
          shape="square"
          aria-label="Auto-layout horizontal"
          onPress={() => onLayout("LR")}
          className="text-gray-600"
        >
          <Icon icon="mdi:arrow-right" className="text-lg" />
        </Button>
      </Tooltip>
      <Tooltip message="Auto-layout vertical">
        <Button
          variant="ghost"
          size="sm"
          shape="square"
          aria-label="Auto-layout vertical"
          onPress={() => onLayout("TB")}
          className="text-gray-600"
        >
          <Icon icon="mdi:arrow-down" className="text-lg" />
        </Button>
      </Tooltip>
    </>
  );
}
