import { classNames } from "@/utils/common";
import { FC, forwardRef, useRef, useState } from "react";
import { useCodeMirror } from "../../hooks/useCodeMirror";
import { MarkdownEditorHeader } from "./markdown-editor-header";
import { MarkdownViewer } from "./markdown-viewer";

type MarkdownEditorProps = {
  className?: string;
  defaultValue?: string;
  disabled?: boolean;
  onChange?: (value: string) => void;
  placeholder?: string;
  id?: string;
};

export const MarkdownEditor: FC<MarkdownEditorProps> = forwardRef<
  HTMLButtonElement,
  MarkdownEditorProps
>(({ id, className = "", defaultValue = "", disabled = false, onChange, placeholder }, ref) => {
  const [isPreviewActive, setPreviewActive] = useState<boolean>(false);
  const [editorText, setEditorText] = useState<string>(defaultValue);
  const codeMirrorRef = useRef<HTMLDivElement>(null);

  const handleTextChange = (value: string) => {
    setEditorText(value);
    if (onChange) onChange(value);
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
    <>
      {id && (
        <button
          id={id}
          ref={ref}
          type="button"
          onClick={() => codeMirror.view?.focus()} // for E2E
          onFocus={() => codeMirror.view?.focus()}
          className="w-0 h-0"
        />
      )}
      <div
        className={classNames(
          `
        bg-white rounded-lg border border-gray-300 shadow-sm
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
    </>
  );
});
