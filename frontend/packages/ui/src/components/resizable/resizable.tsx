import * as ResizablePrimitive from "react-resizable-panels";
import { cn } from "tailwind-variants";

export function ResizablePanelGroup({ className, ...props }: ResizablePrimitive.GroupProps) {
  return (
    <ResizablePrimitive.Group
      className={cn("flex h-full w-full aria-[orientation=vertical]:flex-col", className)}
      {...props}
    />
  );
}

export const ResizablePanel = ResizablePrimitive.Panel;

export function ResizableHandle({ className, ...props }: ResizablePrimitive.SeparatorProps) {
  return (
    <ResizablePrimitive.Separator
      className={cn(
        "w-0.5 rounded-full bg-transparent outline-hidden",
        "aria-[orientation=horizontal]:h-0.5 aria-[orientation=horizontal]:w-full",
        "hover:bg-cyan-600",
        "focus-visible:bg-cyan-600",
        className
      )}
      {...props}
    />
  );
}
