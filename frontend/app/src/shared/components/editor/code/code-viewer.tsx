import { classNames } from "@/shared/utils/common";
import { Light as SyntaxHighlighter, SyntaxHighlighterProps } from "react-syntax-highlighter";
import { atomOneDark } from "react-syntax-highlighter/dist/esm/styles/hljs";

export const CodeViewer = ({ className, children, ...props }: SyntaxHighlighterProps) => {
  return (
    <div className={classNames("rounded-md overflow-hidden text-sm", className)}>
      <SyntaxHighlighter {...props} showLineNumbers style={atomOneDark}>
        {children}
      </SyntaxHighlighter>
    </div>
  );
};
