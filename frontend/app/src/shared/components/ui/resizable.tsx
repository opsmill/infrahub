import * as ResizablePrimitive from "react-resizable-panels";

import { classNames } from "@/shared/utils/common";

export function ResizablePanelGroup({ className, ...props }: ResizablePrimitive.GroupProps) {
  return (
    <ResizablePrimitive.Group
      className={classNames("flex h-full w-full aria-[orientation=vertical]:flex-col", className)}
      {...props}
    />
  );
}

export const ResizablePanel = ResizablePrimitive.Panel;

export function ResizableHandle({ className, ...props }: ResizablePrimitive.SeparatorProps) {
  return (
    <ResizablePrimitive.Separator
      className={classNames(
        "relative w-0.5 bg-transparent outline-hidden",
        "hover:bg-custom-blue-600",
        "focus-visible:bg-custom-blue-600",
        className
      )}
      {...props}
    />
  );
}
