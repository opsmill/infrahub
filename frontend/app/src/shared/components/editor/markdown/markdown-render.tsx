import "@/app/styles/markdown.css";

import type { FC } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { classNames } from "@/shared/utils/common";

type MarkdownRenderProps = {
  className?: string;
  markdownText?: string;
};

export const MarkdownRender: FC<MarkdownRenderProps> = ({ className = "", markdownText = "" }) => (
  <div className={classNames("markdown", className)}>
    <Markdown remarkPlugins={[remarkGfm]}>{markdownText}</Markdown>
  </div>
);
