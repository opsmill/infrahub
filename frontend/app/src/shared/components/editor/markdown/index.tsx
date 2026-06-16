import React from "react";

import { focusWithinStyle } from "@/shared/components/ui/style";
import { useCodeMirror } from "@/shared/hooks/useCodeMirror";
import { classNames } from "@/shared/utils/common";

import { MarkdownEditorHeader } from "./markdown-editor-header";
import { MarkdownRender } from "./markdown-render";

interface MarkdownEditorProps {
  className?: string;
  defaultValue?: string;
  value?: string;
  disabled?: boolean;
  onChange?: (value: string) => void;
  placeholder?: string;
  id?: string;
  ref?: React.Ref<HTMLButtonElement>;
}

export const MarkdownEditor = ({
  value,
  id,
  className = "",
  defaultValue = "",
  disabled = false,
  onChange,
  placeholder,
  ref,
}: MarkdownEditorProps) => {
  const [isPreviewActive, setPreviewActive] = React.useState<boolean>(false);
  // Latches true on the first preview so the rendered markdown stays mounted
  // afterwards. Toggling then only flips visibility, so async (mermaid) content
  // is not re-rendered — avoiding the raw-source flash on every switch.
  const [hasRenderedPreview, setHasRenderedPreview] = React.useState<boolean>(false);
  const codeMirrorRef = React.useRef<HTMLDivElement>(null);

  const handleTextChange = (value: string) => {
    if (onChange) onChange(value);
  };

  const handlePreviewToggle = () => {
    if (!isPreviewActive) setHasRenderedPreview(true);
    setPreviewActive((prev) => !prev);
  };

  const codeMirror = useCodeMirror(codeMirrorRef.current, {
    placeholder,
    defaultValue,
    value,
    onChange: handleTextChange,
  });

  if (disabled) {
    return (
      <MarkdownRender
        markdownText={codeMirror.view?.state?.doc.toString()}
        className="min-h-10 w-full cursor-not-allowed rounded-md bg-gray-100 p-2 text-gray-900 shadow-xs ring-1 ring-gray-300 ring-inset"
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
          className="m-0 block h-0 w-0 p-0"
        />
      )}

      <div
        className={classNames(
          "rounded-md border border-gray-300 bg-white shadow-xs",
          focusWithinStyle,
          className
        )}
      >
        <MarkdownEditorHeader
          codeMirror={codeMirror}
          previewMode={isPreviewActive}
          onPreviewToggle={handlePreviewToggle}
          editLabel="Raw"
        />

        {/* Both views stay mounted and toggle via `hidden` so the rendered
            preview (and CodeMirror) keep their state across switches. The
            preview is mounted lazily on first use to avoid loading its async
            deps until needed. */}
        {hasRenderedPreview && (
          <MarkdownRender
            markdownText={codeMirror.view?.state?.doc.toString()}
            className={classNames("p-2", isPreviewActive ? "" : "hidden")}
          />
        )}
        <div
          ref={codeMirrorRef}
          data-cy="codemirror-editor"
          data-testid="codemirror-editor"
          className={isPreviewActive ? "hidden" : ""}
        />
      </div>
    </>
  );
};
