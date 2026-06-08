import { Icon } from "@iconify-icon/react";
import { ExportMenu, GraphControls, Toolbar } from "@infrahub/graph";
import { Button, Tooltip } from "@infrahub/ui";
import { Panel } from "@xyflow/react";

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
  return (
    <Panel position="bottom-center">
      <Toolbar aria-label="Graph controls" className="mb-4">
        <GraphControls
          edgeStyle={edgeStyle}
          onEdgeStyleChange={onEdgeStyleChange}
          onLayout={onLayout}
        />
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
