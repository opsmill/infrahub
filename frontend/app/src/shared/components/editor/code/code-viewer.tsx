import { classNames } from "@/shared/utils/common";
import SyntaxHighlighter, { SyntaxHighlighterProps } from "react-syntax-highlighter";

export const CodeViewer = ({ className, children, ...props }: SyntaxHighlighterProps) => {
  return (
    <div className={classNames("rounded-md", className)}>
      <SyntaxHighlighter {...props}>{children}</SyntaxHighlighter>
    </div>
  );
};
