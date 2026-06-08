import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { useRef, useState } from "react";
import { cn } from "tailwind-variants";

import { useDismiss } from "../../hooks/use-dismiss";

export type ExportFormat = "png" | "svg";

export interface ExportMenuProps {
  onExport: (format: ExportFormat) => void;
  /** Accessible label for the trigger button. */
  label?: string;
}

/** Export-as-PNG/SVG dropdown for a graph canvas. Self-contained: owns its open state and
 *  outside-click/Escape dismissal. */
export function ExportMenu({ onExport, label = "Export diagram" }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(ref, () => setOpen(false), open);

  const handleExport = (format: ExportFormat) => {
    onExport(format);
    setOpen(false);
  };

  return (
    <div className="relative" ref={ref}>
      <Button
        variant="ghost"
        size="sm"
        shape="square"
        aria-label={label}
        onPress={() => setOpen(!open)}
        className={cn(
          open ? "bg-indigo-500 text-white data-hovered:bg-indigo-600" : "text-gray-600",
        )}
      >
        <Icon icon="mdi:download" className="text-lg" />
      </Button>
      {open && (
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
  );
}
