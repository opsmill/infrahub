import "./mermaid-diagram.css";

import {
  type DiagramType,
  detectType,
  load,
  PeleError,
  type RenderOptions,
  type RenderResult,
  registered,
  render,
} from "pele/lazy";
import React from "react";

import { PanZoom } from "@/shared/components/display/pan-zoom";
import { DiagramError } from "@/shared/components/editor/markdown/diagram-error";

const RENDER_OPTIONS: RenderOptions = {
  images: false,
  fontFamily: "InterVariable, sans-serif",
};

// Pele's `load` starts a new download after a failed one, so typeLoads keeps the failed promise for `React.use` to throw instead of retrying forever.
const typeLoads = new Map<DiagramType, Promise<boolean>>();

function loadDiagramType(type: DiagramType): Promise<boolean> {
  const pending = typeLoads.get(type) ?? load(type);
  typeLoads.set(type, pending);
  return pending;
}

function detectDiagramType(source: string): DiagramType | null {
  try {
    return detectType(source);
  } catch {
    return null;
  }
}

function renderDiagram(source: string, idPrefix: string): RenderResult | PeleError {
  try {
    return render(source, { ...RENDER_OPTIONS, idPrefix });
  } catch (error) {
    if (error instanceof PeleError) return error;
    throw error;
  }
}

interface MermaidDiagramContentProps {
  source: string;
}

export default function MermaidDiagramContent({ source }: MermaidDiagramContentProps) {
  const idPrefix = React.useId().replace(/[^\w-]/g, "");
  const type = detectDiagramType(source);
  if (type && !registered(type)) React.use(loadDiagramType(type));

  const diagram = renderDiagram(source, idPrefix);
  if (diagram instanceof PeleError)
    return <DiagramError message={diagram.message} source={source} />;

  return (
    <PanZoom className="bg-background">
      <div
        className="w-full pt-9 [&>svg]:mx-auto"
        // biome-ignore lint/security/noDangerouslySetInnerHtml: Pele escapes diagram text, emits no scripts or event handlers, and drops javascript: links.
        dangerouslySetInnerHTML={{ __html: diagram.svg }}
      />
    </PanZoom>
  );
}
