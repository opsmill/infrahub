import { FC } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { classNames } from "../../utils/common";
import "../styles/markdown.css";

type MarkdownViewerProps = {
  className?: string;
  markdownText?: string;
};

export const MarkdownViewer: FC<MarkdownViewerProps> = ({ className = "", markdownText }) => (
  <Markdown remarkPlugins={[remarkGfm]} className={classNames("markdown", className)}>
    {markdownText}
  </Markdown>
);
