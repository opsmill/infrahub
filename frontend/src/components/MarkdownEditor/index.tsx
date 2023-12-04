import React, { forwardRef, useState } from "react";
import { MarkdownViewer } from "../MarkdownViewer";
import { classNames } from "../../utils/common";
import { CodeMirror } from "./CodeMirror";
import { Button } from "../button";

type MarkdownEditorProps = {
  className?: string;
  defaultValue?: string;
  onChange: (v: string) => void;
};
export const MarkdownEditor = forwardRef<HTMLDivElement, MarkdownEditorProps>(
  ({ className = "", defaultValue = "", onChange }, ref) => {
    const [preview, setPreview] = useState<boolean>(false);
    const [text, setText] = useState<string>(defaultValue);

    return (
      <div ref={ref} className={classNames("rounded-md border border-gray-300", className)}>
        <Button
          onClick={() => setPreview(!preview)}
          className="bg-white border-none rounded-none rounded-tl-md">
          {preview ? "Continue editing" : "Preview"}
        </Button>

        {preview ? (
          <MarkdownViewer markdownText={text} />
        ) : (
          <CodeMirror
            placeholder="Write your text here..."
            value={text}
            onChange={(e) => {
              onChange(e);
              setText(e);
            }}
          />
        )}
      </div>
    );
  }
);
