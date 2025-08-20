import "@/app/styles/markdown.css";
import { classNames } from "@/shared/utils/common";
import { FC } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownRenderProps = {
  className?: string;
  markdownText?: string;
};

export const MarkdownRender: FC<MarkdownRenderProps> = ({ className = "", markdownText = "" }) => (
  <div className={classNames("markdown", className)}>
    <Markdown remarkPlugins={[remarkGfm]}>{markdownText}</Markdown>
  </div>
);
