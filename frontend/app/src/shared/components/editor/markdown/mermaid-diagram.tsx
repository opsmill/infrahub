import { Spinner } from "@infrahub/ui";
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
import { Suspense, use, useId } from "react";
import { ErrorBoundary } from "react-error-boundary";

import { PanZoom } from "@/shared/components/display/pan-zoom";

const LOAD_FAILED = "Could not load the diagram. Reload the page to try again.";

const RENDER_OPTIONS: RenderOptions = {
  // Diagrams come from user-written Markdown, so they may not link out or load remote images.
  links: false,
  images: false,
  fontFamily: "InterVariable, sans-serif",
};

// One promise per diagram type, so `use` sees the same promise on every render.
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

type DiagramErrorProps = {
  message: string;
  source: string;
};

function DiagramError({ message, source }: DiagramErrorProps) {
  return (
    <div>
      <div className="mermaid-error rounded-md p-2 font-mono text-sm">{message}</div>
      <pre>
        <code>{source}</code>
      </pre>
    </div>
  );
}

type MermaidDiagramProps = {
  source: string;
};

function DiagramSvg({ source }: MermaidDiagramProps) {
  const idPrefix = useId().replace(/[^\w-]/g, "");
  const type = detectDiagramType(source);
  if (type && !registered(type)) use(loadDiagramType(type));

  const diagram = renderDiagram(source, idPrefix);
  if (diagram instanceof PeleError)
    return <DiagramError message={diagram.message} source={source} />;

  return (
    <PanZoom className="bg-background">
      {/* The zoom buttons overlay the top edge, and a diagram fills the full width. */}
      <div
        className="w-full pt-9"
        // biome-ignore lint/security/noDangerouslySetInnerHtml: Pele escapes diagram text and emits no scripts or event handlers, and links and images are turned off.
        dangerouslySetInnerHTML={{ __html: diagram.svg }}
      />
    </PanZoom>
  );
}

export function MermaidDiagram({ source }: MermaidDiagramProps) {
  return (
    <ErrorBoundary
      fallback={<DiagramError message={LOAD_FAILED} source={source} />}
      resetKeys={[source]}
    >
      <Suspense fallback={<Spinner className="mx-auto h-40" />}>
        <DiagramSvg source={source} />
      </Suspense>
    </ErrorBoundary>
  );
}
