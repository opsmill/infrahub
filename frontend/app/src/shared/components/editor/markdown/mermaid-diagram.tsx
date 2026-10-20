import type React from "react";
import type { ExtraProps } from "react-markdown";

import { PanZoom } from "@/shared/components/display/pan-zoom";

type MermaidDiagramProps = React.ComponentProps<"svg"> & ExtraProps;

// Rendered as react-markdown's `svg` override. rehype-mermaid emits the diagram
// as an <svg id="mermaid-…">; wrap those in a pan/zoom container with controls.
// Any other svg is passed through untouched.
export function MermaidDiagram({ node: _node, ...svgProps }: MermaidDiagramProps) {
  if (!String(svgProps.id ?? "").startsWith("mermaid")) {
    return <svg {...svgProps} />;
  }

  return (
    <PanZoom className="bg-background">
      <svg {...svgProps} />
    </PanZoom>
  );
}
