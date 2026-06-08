import { Icon } from "@iconify-icon/react";
import { Toolbar, useDismiss } from "@infrahub/graph";
import { Button } from "@infrahub/ui";
import { Panel, useReactFlow } from "@xyflow/react";
import { useRef, useState } from "react";

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
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  const handleExport = (format: ExportFormat) => {
    onExport(format);
    setExportMenuOpen(false);
  };

  function closeExportMenu() {
    setExportMenuOpen(false);
  }
  useDismiss(exportMenuRef, closeExportMenu, exportMenuOpen);

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
        <div className="relative" ref={exportMenuRef}>
          <Tooltip message="Export diagram">
            <Button
              variant="ghost"
              size="sm"
              shape="square"
              aria-label="Export diagram"
              onPress={() => setExportMenuOpen(!exportMenuOpen)}
              className={classNames(
                exportMenuOpen
                  ? "bg-indigo-500 text-white data-hovered:bg-indigo-600"
                  : "text-gray-600"
              )}
            >
              <Icon icon="mdi:download" className="text-lg" />
            </Button>
          </Tooltip>
          {exportMenuOpen && (
            <div className="absolute bottom-full left-1/2 mb-2 min-w-[120px] -translate-x-1/2 rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
              <Button
                variant="ghost"
                size="sm"
                onPress={() => handleExport("png")}
                className="w-full justify-start rounded-none px-3 py-2 text-gray-700 text-sm"
              >
                <Icon icon="mdi:image-outline" className="text-gray-500 text-lg" />
                PNG
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onPress={() => handleExport("svg")}
                className="w-full justify-start rounded-none px-3 py-2 text-gray-700 text-sm"
              >
                <Icon icon="mdi:file-code-outline" className="text-gray-500 text-lg" />
                SVG
              </Button>
            </div>
          )}
        </div>
      </Toolbar>
    </Panel>
  );
}
