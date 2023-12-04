import React, { FC } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "../styles/markdown.css";

type MarkdownViewerProps = {
  markdownText?: string;
};

export const MarkdownViewer: FC<MarkdownViewerProps> = ({ markdownText }) => {
  return (
    <Markdown remarkPlugins={[remarkGfm]} className="markdown">
      {markdownText}
    </Markdown>
  );
};
