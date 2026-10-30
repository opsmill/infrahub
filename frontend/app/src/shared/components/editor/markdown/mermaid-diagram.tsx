import { Spinner } from "@infrahub/ui";
import React from "react";
import { ErrorBoundary } from "react-error-boundary";

import { MermaidDiagramError } from "@/shared/components/editor/markdown/mermaid-diagram-error";

const MermaidDiagramContent = React.lazy(() => import("./mermaid-diagram-content"));

const LOAD_FAILED = "Could not load the diagram. Reload the page to try again.";

interface MermaidDiagramProps {
  source: string;
}

export function MermaidDiagram({ source }: MermaidDiagramProps) {
  return (
    <ErrorBoundary
      fallback={<MermaidDiagramError message={LOAD_FAILED} source={source} />}
      resetKeys={[source]}
    >
      <React.Suspense fallback={<Spinner className="mx-auto h-40" />}>
        <MermaidDiagramContent source={source} />
      </React.Suspense>
    </ErrorBoundary>
  );
}
