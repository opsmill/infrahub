import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import { useId, useRef, useState } from "react";
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
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  useDismiss(
    ref,
    (event) => {
      setOpen(false);
      // Escape returns focus to the trigger; outside clicks leave focus where the user pointed.
      if (event instanceof KeyboardEvent) {
        triggerRef.current?.focus();
      }
    },
    open
  );

  const handleExport = (format: ExportFormat) => {
    // Always close the menu, even if the consumer's onExport throws — otherwise the
    // dropdown is left open in an inconsistent state.
    try {
      onExport(format);
    } finally {
      setOpen(false);
      triggerRef.current?.focus();
    }
  };

  return (
    <div className="relative" ref={ref}>
      <Tooltip message={label}>
        <Button
          ref={triggerRef}
          variant="ghost"
          size="sm"
          shape="square"
          aria-label={label}
          aria-expanded={open}
          aria-controls={open ? menuId : undefined}
          onPress={() => setOpen(!open)}
          className={cn(
            open
              ? "bg-selected text-selected-foreground shadow-selected data-hovered:bg-selected-highlight"
              : "text-subtle"
          )}
        >
          <Icon icon="mdi:download" className="text-lg" />
        </Button>
      </Tooltip>
      {open && (
        <div
          id={menuId}
          className="absolute bottom-full left-1/2 mb-2 min-w-[120px] -translate-x-1/2 rounded-lg border bg-popover py-1 shadow-lg backdrop-blur-lg"
        >
          <Button
            // Moving focus into the menu on open is the WAI-ARIA menu pattern, not a page-load autofocus.
            autoFocus
            variant="ghost"
            size="sm"
            onPress={() => handleExport("png")}
            className="w-full justify-start rounded-none px-3 py-2 text-sm text-subtle"
          >
            <Icon icon="mdi:image-outline" className="text-lg text-subtle-muted" />
            PNG
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onPress={() => handleExport("svg")}
            className="w-full justify-start rounded-none px-3 py-2 text-sm text-subtle"
          >
            <Icon icon="mdi:file-code-outline" className="text-lg text-subtle-muted" />
            SVG
          </Button>
        </div>
      )}
    </div>
  );
}
