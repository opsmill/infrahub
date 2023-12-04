import React, { forwardRef, useState } from "react";
import { MarkdownViewer } from "../MarkdownViewer";
import { classNames } from "../../utils/common";
import { CodeMirror } from "./CodeMirror";
import { Button } from "../button";

type MarkdownEditorProps = {
  className?: string;
  value?: string;
};
export const MarkdownEditor = forwardRef<HTMLDivElement, MarkdownEditorProps>(
  ({ className = "", value }, ref) => {
    const [preview, setPreview] = useState<boolean>(false);

    return (
      <div ref={ref} className={classNames("rounded-md border border-gray-300 shadow", className)}>
        <Button
          onClick={() => setPreview(!preview)}
          className="bg-white border-none rounded-none rounded-tl-md">
          {preview ? "Continue editing" : "Preview"}
        </Button>

        {preview ? (
          <MarkdownViewer markdownText={value} />
        ) : (
          <CodeMirror placeholder="Write your text here..." value={value} />
        )}
      </div>
    );
  }
);
