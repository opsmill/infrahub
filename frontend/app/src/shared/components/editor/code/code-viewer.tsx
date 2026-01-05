import { Prism as SyntaxHighlighter, type SyntaxHighlighterProps } from "react-syntax-highlighter";
import { darcula } from "react-syntax-highlighter/dist/esm/styles/prism";

import { classNames } from "@/shared/utils/common";

export const CodeViewer = ({ className, children, ...props }: SyntaxHighlighterProps) => {
  return (
    <div className={classNames("overflow-hidden rounded-md text-sm", className)}>
      <SyntaxHighlighter {...props} showLineNumbers style={darcula}>
        {children}
      </SyntaxHighlighter>
    </div>
  );
};
