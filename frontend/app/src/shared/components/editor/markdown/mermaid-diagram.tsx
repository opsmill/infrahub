import { Button } from "@infrahub/ui";
import { RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import type React from "react";
import type { ExtraProps } from "react-markdown";
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";

type MermaidDiagramProps = React.ComponentProps<"svg"> & ExtraProps;

// Rendered as react-markdown's `svg` override. rehype-mermaid emits the diagram
// as an <svg id="mermaid-…">; wrap those in a pan/zoom container with controls.
// Any other svg is passed through untouched.
export function MermaidDiagram({ node: _node, ...svgProps }: MermaidDiagramProps) {
  if (!String(svgProps.id ?? "").startsWith("mermaid")) {
    return <svg {...svgProps} />;
  }

  return (
    <div className="relative bg-white">
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
              <svg {...svgProps} />
            </TransformComponent>
          </>
        )}
      </TransformWrapper>
    </div>
  );
}
