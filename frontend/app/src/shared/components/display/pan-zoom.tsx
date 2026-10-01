import { Button } from "@infrahub/ui";
import { RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import type React from "react";
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";

import { classNames } from "@/shared/utils/common";

export interface PanZoomProps {
  children: React.ReactNode;
  className?: string;
}

export function PanZoom({ children, className }: PanZoomProps) {
  return (
    <div className={classNames("relative", className)}>
      <TransformWrapper minScale={0.5} maxScale={8} centerOnInit wheel={{ step: 0.1 }}>
        {({ zoomIn, zoomOut, resetTransform }) => (
          <>
            <div className="absolute top-1 right-1 z-10 flex gap-1">
              <Button
                variant="outline"
                size="xs"
                shape="square"
                onPress={() => zoomIn()}
                aria-label="Zoom in"
              >
                <ZoomIn />
              </Button>
              <Button
                variant="outline"
                size="xs"
                shape="square"
                onPress={() => zoomOut()}
                aria-label="Zoom out"
              >
                <ZoomOut />
              </Button>
              <Button
                variant="outline"
                size="xs"
                shape="square"
                onPress={() => resetTransform()}
                aria-label="Reset zoom"
              >
                <RotateCcw />
              </Button>
            </div>
            <TransformComponent wrapperClass="!w-full" contentClass="!w-full">
              {children}
            </TransformComponent>
          </>
        )}
      </TransformWrapper>
    </div>
  );
}
