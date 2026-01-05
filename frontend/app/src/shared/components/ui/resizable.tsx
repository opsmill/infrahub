import type React from "react";
import * as ResizablePrimitive from "react-resizable-panels";

import { classNames } from "@/shared/utils/common";

export const ResizablePanelGroup = ({
  className,
  ...props
}: React.ComponentProps<typeof ResizablePrimitive.PanelGroup>) => (
  <ResizablePrimitive.PanelGroup
    className={classNames(
      "flex h-full w-full data-[panel-group-direction=vertical]:flex-col",
      className
    )}
    {...props}
  />
);

export const ResizablePanel = ResizablePrimitive.Panel;

export const ResizableHandle = ({
  className,
  ...props
}: React.ComponentProps<typeof ResizablePrimitive.PanelResizeHandle>) => (
  <ResizablePrimitive.PanelResizeHandle
    className={classNames(
      "relative w-0.5 bg-transparent outline-hidden",
      "hover:bg-custom-blue-600",
      "focus-visible:bg-custom-blue-600",
      className
    )}
    {...props}
  ></ResizablePrimitive.PanelResizeHandle>
);
