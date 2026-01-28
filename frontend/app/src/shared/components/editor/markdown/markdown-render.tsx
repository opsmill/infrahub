import "@/app/styles/markdown.css";

import type { FC } from "react";
import Markdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { classNames } from "@/shared/utils/common";

type MarkdownRenderProps = {
  className?: string;
  markdownText?: string;
};

export const MarkdownRender: FC<MarkdownRenderProps> = ({ className = "", markdownText = "" }) => (
  <div className={classNames("markdown", className)}>
    <Markdown remarkPlugins={[remarkGfm, remarkBreaks]}>{markdownText}</Markdown>
  </div>
);
