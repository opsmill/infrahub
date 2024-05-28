import { useRef } from "react";
import { useCodeMirror } from "../../../hooks/useCodeMirror";
import { CodeViewerLimiter } from "../code-viewer-limiter";

type GraphqlViewerProps = {
  value?: string;
  limitHeight?: boolean;
};

export const GraphqlViewer = ({ value, limitHeight = false }: GraphqlViewerProps) => {
  const codeMirrorRef = useRef<HTMLDivElement>(null);
  useCodeMirror(codeMirrorRef.current, {
    lang: "graphql",
    readOnly: true,
    value,
  });

  if (limitHeight) {
    return (
      <CodeViewerLimiter>
        <div ref={codeMirrorRef} />
      </CodeViewerLimiter>
    );
  }

  return <div ref={codeMirrorRef} />;
};
