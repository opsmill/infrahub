import React, { FC, useRef, useState } from "react";
import { MarkdownEditorHeader } from "./MarkdownEditorHeader";
import { MarkdownViewer } from "../MarkdownViewer";
import { classNames } from "../../utils/common";
import { useCodeMirror } from "../../hooks/useCodeMirror";

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
  const codeMirrorRef = useRef<HTMLDivElement>(null);

  const handleTextChange = (value: string) => {
    setEditorText(value);
    onChange(value);
  };

  const codeMirror = useCodeMirror(codeMirrorRef.current, {
    placeholder,
    value: editorText,
    onChange: handleTextChange,
  });

  if (disabled) {
    return (
      <MarkdownViewer
        markdownText={editorText}
        className="w-full bg-gray-100 min-h-10 rounded-md p-2 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 cursor-not-allowed"
      />
    );
  }

  return (
    <div
      className={classNames(
        `
        bg-white rounded-lg border border-gray-200
        focus-within:outline focus-within:outline-custom-blue-600 focus-within:border-custom-blue-600
        `,
        className
      )}>
      <MarkdownEditorHeader
        codeMirror={codeMirror}
        previewMode={isPreviewActive}
        onPreviewToggle={() => setPreviewActive((prev) => !prev)}
      />

      {isPreviewActive ? (
        <MarkdownViewer markdownText={editorText} className="p-2" />
      ) : (
        <div ref={codeMirrorRef} data-cy="codemirror-editor" data-testid="codemirror-editor" />
      )}
    </div>
  );
};
