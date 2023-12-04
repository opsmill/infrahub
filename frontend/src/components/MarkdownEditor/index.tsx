import React, { FC, useRef, useState } from "react";
import { MarkdownEditorHeader } from "./MarkdownEditorHeader";
import { MarkdownViewer } from "../MarkdownViewer";
import { classNames } from "../../utils/common";
import { CodeMirror, CodeMirrorType } from "./CodeMirrorType";

type MarkdownEditorProps = {
  className?: string;
  defaultValue?: string;
  disabled?: boolean;
  onChange: (v: string) => void;
};
export const MarkdownEditor: FC<MarkdownEditorProps> = ({
  className = "",
  defaultValue = "",
  disabled = false,
  onChange,
}) => {
  const [preview, setPreview] = useState<boolean>(false);
  const [text, setText] = useState<string>(defaultValue);
  const codeMirrorRef = useRef<CodeMirrorType>({ editor: null });

  if (disabled) {
    return (
      <MarkdownViewer
        markdownText={text}
        className="w-full bg-gray-100 min-h-10 rounded-md p-2 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 cursor-not-allowed"
      />
    );
  }

  return (
    <div className={classNames("rounded-md border border-gray-300", className)}>
      <MarkdownEditorHeader
        codeMirror={codeMirrorRef.current}
        preview={preview}
        onPreviewToggle={() => setPreview(!preview)}
      />

      {preview ? (
        <MarkdownViewer markdownText={text} />
      ) : (
        <CodeMirror
          ref={codeMirrorRef}
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
};
