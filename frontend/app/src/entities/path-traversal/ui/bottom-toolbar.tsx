import { Icon } from "@iconify-icon/react";
import { Panel, useReactFlow } from "@xyflow/react";
import { useRef, useState } from "react";

import { classNames } from "@/shared/utils/common";

import type { EdgeStyle } from "./path-edge";
import { useDismiss } from "./use-dismiss";

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
    <Panel
      position="bottom-center"
      className="mb-4 flex items-center gap-2 rounded-lg bg-white px-3 py-2 shadow-lg"
    >
      <button
        type="button"
        onClick={() => zoomOut()}
        className="flex h-8 w-8 items-center justify-center rounded text-gray-600 hover:bg-gray-100"
        title="Zoom out"
      >
        <Icon icon="mdi:minus" className="text-lg" />
      </button>
      <button
        type="button"
        onClick={() => fitView({ padding: 0.2 })}
        className="flex h-8 w-8 items-center justify-center rounded text-gray-600 hover:bg-gray-100"
        title="Fit to screen"
      >
        <Icon icon="mdi:fit-to-screen" className="text-lg" />
      </button>
      <button
        type="button"
        onClick={() => zoomIn()}
        className="flex h-8 w-8 items-center justify-center rounded text-gray-600 hover:bg-gray-100"
        title="Zoom in"
      >
        <Icon icon="mdi:plus" className="text-lg" />
      </button>
      <div className="mx-2 h-6 w-px bg-gray-200" />
      <button
        type="button"
        onClick={() => onEdgeStyleChange(edgeStyle === "bezier" ? "smoothstep" : "bezier")}
        className="flex h-8 items-center justify-center gap-1.5 rounded px-2 text-gray-600 hover:bg-gray-100"
        title={`Switch to ${edgeStyle === "bezier" ? "step" : "smooth"} edges`}
      >
        <Icon
          icon={edgeStyle === "bezier" ? "mdi:vector-curve" : "mdi:vector-polyline"}
          className="text-lg"
        />
        <span className="text-xs">{edgeStyle === "bezier" ? "Smooth" : "Step"}</span>
      </button>
      <div className="mx-2 h-6 w-px bg-gray-200" />
      <button
        type="button"
        onClick={() => onLayout("LR")}
        className="flex h-8 w-8 items-center justify-center rounded text-gray-600 hover:bg-gray-100"
        title="Auto-layout horizontal"
      >
        <Icon icon="mdi:arrow-right" className="text-lg" />
      </button>
      <button
        type="button"
        onClick={() => onLayout("TB")}
        className="flex h-8 w-8 items-center justify-center rounded text-gray-600 hover:bg-gray-100"
        title="Auto-layout vertical"
      >
        <Icon icon="mdi:arrow-down" className="text-lg" />
      </button>
      <div className="mx-2 h-6 w-px bg-gray-200" />
      <button
        type="button"
        onClick={onParametersClick}
        className={classNames(
          "flex h-8 w-8 items-center justify-center rounded",
          isParametersOpen
            ? "bg-indigo-500 text-white hover:bg-indigo-600"
            : "text-gray-600 hover:bg-gray-100"
        )}
        title={isParametersOpen ? "Hide parameters" : "Show parameters"}
      >
        <Icon icon="mdi:tune-variant" className="text-lg" />
      </button>
      {onReload && (
        <button
          type="button"
          onClick={onReload}
          disabled={isReloading}
          className="flex h-8 w-8 items-center justify-center rounded text-gray-600 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50"
          title="Reload"
        >
          <Icon
            icon="mdi:refresh"
            className={classNames("text-lg", isReloading && "animate-spin")}
          />
        </button>
      )}
      <div className="mx-2 h-6 w-px bg-gray-200" />
      <div className="relative" ref={exportMenuRef}>
        <button
          type="button"
          onClick={() => setExportMenuOpen(!exportMenuOpen)}
          className={classNames(
            "flex h-8 w-8 items-center justify-center rounded",
            exportMenuOpen
              ? "bg-indigo-500 text-white hover:bg-indigo-600"
              : "text-gray-600 hover:bg-gray-100"
          )}
          title="Export diagram"
        >
          <Icon icon="mdi:download" className="text-lg" />
        </button>
        {exportMenuOpen && (
          <div className="absolute bottom-full left-1/2 mb-2 min-w-[120px] -translate-x-1/2 rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
            <button
              type="button"
              onClick={() => handleExport("png")}
              className="flex w-full items-center gap-2 px-3 py-2 text-gray-700 text-sm hover:bg-gray-100"
            >
              <Icon icon="mdi:image-outline" className="text-gray-500 text-lg" />
              PNG
            </button>
            <button
              type="button"
              onClick={() => handleExport("svg")}
              className="flex w-full items-center gap-2 px-3 py-2 text-gray-700 text-sm hover:bg-gray-100"
            >
              <Icon icon="mdi:file-code-outline" className="text-gray-500 text-lg" />
              SVG
            </button>
          </div>
        )}
      </div>
    </Panel>
  );
}
