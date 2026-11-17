import { Spinner } from "@infrahub/ui";
import React from "react";
import { ErrorBoundary } from "react-error-boundary";

import { MermaidDiagramError } from "@/shared/components/editor/markdown/mermaid-diagram-error";

const MermaidDiagramContent = React.lazy(() => import("./mermaid-diagram-content"));

const LOAD_FAILED = "Could not load the diagram. Reload the page to try again.";

interface MermaidDiagramProps {
  code: string;
}

export function MermaidDiagram({ code }: MermaidDiagramProps) {
  return (
    <ErrorBoundary
      fallback={<MermaidDiagramError message={LOAD_FAILED} code={code} />}
      resetKeys={[code]}
    >
      <React.Suspense fallback={<Spinner className="mx-auto h-40" />}>
        <MermaidDiagramContent code={code} />
      </React.Suspense>
    </ErrorBoundary>
  );
}
