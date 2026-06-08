import { Icon } from "@iconify-icon/react";
import { ExportMenu, Toolbar } from "@infrahub/graph";
import { Button } from "@infrahub/ui";
import { Panel, useReactFlow } from "@xyflow/react";

import { Tooltip } from "@/shared/components/aria/tooltip";
import { classNames } from "@/shared/utils/common";

import type { EdgeStyle } from "./path-edge";

export type LayoutDirection = "TB" | "LR";
export type ExportFormat = "png" | "svg";

export type BottomToolbarProps = {
  onParametersClick: () => void;
  isParametersOpen: boolean;
  edgeStyle: EdgeStyle;
  onEdgeStyleChange: (style: EdgeStyle) => void;
  onLayout: (direction: LayoutDirection) => void;
  onExport: (format: ExportFormat) => void;
  onReload?: () => void;
  isReloading?: boolean;
};

export function BottomToolbar({
  onParametersClick,
  isParametersOpen,
  edgeStyle,
  onEdgeStyleChange,
  onLayout,
  onExport,
  onReload,
  isReloading,
}: BottomToolbarProps) {
  const { zoomIn, zoomOut, fitView } = useReactFlow();

  return (
    <Panel position="bottom-center">
      <Toolbar aria-label="Graph controls" className="mb-4">
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
        <Toolbar.Divider className="mx-2" />
        <Tooltip message={isParametersOpen ? "Hide parameters" : "Show parameters"}>
          <Button
            variant="ghost"
            size="sm"
            shape="square"
            aria-label={isParametersOpen ? "Hide parameters" : "Show parameters"}
            onPress={onParametersClick}
            className={classNames(
              isParametersOpen
                ? "bg-indigo-500 text-white data-hovered:bg-indigo-600"
                : "text-gray-600"
            )}
          >
            <Icon icon="mdi:tune-variant" className="text-lg" />
          </Button>
        </Tooltip>
        {onReload && (
          <Tooltip message="Reload">
            <Button
              variant="ghost"
              size="sm"
              shape="square"
              aria-label="Reload"
              onPress={onReload}
              isDisabled={isReloading}
              className="text-gray-600"
            >
              <Icon
                icon="mdi:refresh"
                className={classNames("text-lg", isReloading && "animate-spin")}
              />
            </Button>
          </Tooltip>
        )}
        <Toolbar.Divider className="mx-2" />
        <ExportMenu onExport={onExport} />
      </Toolbar>
    </Panel>
  );
}
