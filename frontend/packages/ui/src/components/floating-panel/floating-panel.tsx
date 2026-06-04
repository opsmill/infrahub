import { X } from "lucide-react";
import { type ReactNode, useRef } from "react";
import { cn } from "tailwind-variants";

import { useDismiss } from "../../hooks/use-dismiss";
import { Card, CardContent, CardHeader } from "../card/card";
import { IconButton } from "../icon-button/icon-button";

export interface FloatingPanelProps {
  title: ReactNode;
  description?: ReactNode;
  onClose: () => void;
  /** Defaults to true. When false the panel renders nothing. */
  isOpen?: boolean;
  /** When true, outside-click and Escape call onClose. Defaults to false. */
  dismissable?: boolean;
  /** Positioning + sizing classes supplied by the consumer (e.g. absolute inset/width). */
  className?: string;
  /** Optional extra header row rendered below the title (e.g. tabs). */
  headerContent?: ReactNode;
  /** Accessible label for the close button. */
  closeLabel?: string;
  children: ReactNode;
}

export function FloatingPanel({
  title,
  description,
  onClose,
  isOpen = true,
  dismissable = false,
  className,
  headerContent,
  closeLabel = "Close panel",
  children,
}: FloatingPanelProps) {
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(ref, onClose, isOpen && dismissable);

  if (!isOpen) return null;

  return (
    <Card ref={ref} className={cn("overflow-hidden", className)}>
      <CardHeader className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="font-semibold text-lg text-neutral-900">{title}</h2>
            {description && <p className="mt-1 text-neutral-500 text-sm">{description}</p>}
          </div>
          <IconButton
            aria-label={closeLabel}
            size="xs"
            onPress={onClose}
            className="-mt-1 -mr-1 text-neutral-400"
          >
            <X className="size-4" />
          </IconButton>
        </div>
        {headerContent}
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto p-0">{children}</CardContent>
    </Card>
  );
}
