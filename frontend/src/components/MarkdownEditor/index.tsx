import React, { forwardRef, useState } from "react";
import { MarkdownEditorHeader } from "./MarkdownEditorHeader";
import { MarkdownViewer } from "../MarkdownViewer";
import { classNames } from "../../utils/common";
import { CodeMirror } from "./CodeMirror";

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
        <MarkdownEditorHeader preview={preview} onPreviewToggle={() => setPreview(!preview)} />

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
