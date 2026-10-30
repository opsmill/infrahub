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
import { MermaidDiagramError } from "@/shared/components/editor/markdown/mermaid-diagram-error";

const RENDER_OPTIONS: RenderOptions = {
  images: false,
  fontFamily: "InterVariable, sans-serif",
};

// Pele's `load` starts a new download after a failed one, so typeLoads keeps the failed promise for `React.use` to throw instead of retrying forever.
const typeLoads = new Map<DiagramType, Promise<boolean>>();

// A render retried after suspending must call `React.use` again, so a type loaded here keeps its promise even once registered.
function getTypeLoad(type: DiagramType | null): Promise<boolean> | null {
  if (!type) return null;
  const pending = typeLoads.get(type) ?? (registered(type) ? null : load(type));
  if (pending) typeLoads.set(type, pending);
  return pending;
}

function detectDiagramType(code: string): DiagramType | null {
  try {
    return detectType(code);
  } catch {
    return null;
  }
}

function renderDiagram(code: string, idPrefix: string): RenderResult | PeleError {
  try {
    return render(code, { ...RENDER_OPTIONS, idPrefix });
  } catch (error) {
    if (error instanceof PeleError) return error;
    throw error;
  }
}

interface MermaidDiagramContentProps {
  code: string;
}

export default function MermaidDiagramContent({ code }: MermaidDiagramContentProps) {
  const idPrefix = React.useId().replace(/[^\w-]/g, "");
  const typeLoad = getTypeLoad(detectDiagramType(code));
  if (typeLoad) React.use(typeLoad);

  const diagram = renderDiagram(code, idPrefix);
  if (diagram instanceof PeleError)
    return <MermaidDiagramError message={diagram.message} code={code} />;

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
