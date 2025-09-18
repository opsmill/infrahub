import { type FC, forwardRef, useRef, useState } from "react";

import { focusWithinStyle } from "@/shared/components/ui/style";
import { useCodeMirror } from "@/shared/hooks/useCodeMirror";
import { classNames } from "@/shared/utils/common";

import { MarkdownEditorHeader } from "./markdown-editor-header";
import { MarkdownRender } from "./markdown-render";

type MarkdownEditorProps = {
  className?: string;
  defaultValue?: string;
  value?: string;
  disabled?: boolean;
  onChange?: (value: string) => void;
  placeholder?: string;
  id?: string;
};

export const MarkdownEditor: FC<MarkdownEditorProps> = forwardRef<
  HTMLButtonElement,
  MarkdownEditorProps
>(
  (
    { value, id, className = "", defaultValue = "", disabled = false, onChange, placeholder },
    ref
  ) => {
    const [isPreviewActive, setPreviewActive] = useState<boolean>(false);
    const codeMirrorRef = useRef<HTMLDivElement>(null);

    const handleTextChange = (value: string) => {
      if (onChange) onChange(value);
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
            onPreviewToggle={() => setPreviewActive((prev) => !prev)}
            editLabel="Raw"
          />

          {isPreviewActive ? (
            <MarkdownRender markdownText={codeMirror.view?.state?.doc.toString()} className="p-2" />
          ) : (
            <div ref={codeMirrorRef} data-cy="codemirror-editor" data-testid="codemirror-editor" />
          )}
        </div>
      </>
    );
  }
);
