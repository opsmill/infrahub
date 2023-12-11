import React, { FC, useRef, useState } from "react";
import { MarkdownEditorHeader } from "./MarkdownEditorHeader";
import { MarkdownViewer } from "../MarkdownViewer";
import { classNames } from "../../utils/common";
import { CodeMirror, CodeMirrorType } from "./CodeMirror";

type MarkdownEditorProps = {
  className?: string;
  defaultValue?: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  placeholder?: string;
};

export const MarkdownEditor: FC<MarkdownEditorProps> = ({
  className = "",
  defaultValue = "",
  disabled = false,
  onChange,
  placeholder,
}) => {
  const [isPreviewActive, setPreviewActive] = useState<boolean>(false);
  const [editorText, setEditorText] = useState<string>(defaultValue);
  const codeMirrorRef = useRef<CodeMirrorType>({ editor: null });

  if (disabled) {
    return (
      <MarkdownViewer
        markdownText={editorText}
        className="w-full bg-gray-100 min-h-10 rounded-md p-2 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 cursor-not-allowed"
      />
    );
  }

  const handleTextChange = (value: string) => {
    setEditorText(value);
    onChange(value);
  };

  return (
    <div className={classNames("bg-white rounded-lg border border-gray-200", className)}>
      <MarkdownEditorHeader
        codeMirror={codeMirrorRef.current}
        previewMode={isPreviewActive}
        onPreviewToggle={() => setPreviewActive((prev) => !prev)}
      />

      {isPreviewActive ? (
        <MarkdownViewer markdownText={editorText} className="p-2" />
      ) : (
        <CodeMirror
          ref={codeMirrorRef}
          placeholder={placeholder}
          value={editorText}
          onChange={handleTextChange}
        />
      )}
    </div>
  );
};
