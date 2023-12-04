import React, { FC } from "react";
import { MarkdownEditor } from "./MarkdownEditor";

type TextareaWithEditorProps = {
  className?: string;
  defaultValue?: string;
  disabled?: Boolean;
  error?: { message: string };
  onChange?: (v: string) => void;
};
export const TextareaWithEditor: FC<TextareaWithEditorProps> = ({
  className,
  defaultValue,
  disabled,
  error,
  onChange,
}) => {
  return (
    <div className="relative">
      <MarkdownEditor
        className={className}
        disabled={disabled}
        onChange={onChange}
        value={defaultValue}
      />

      {error?.message && (
        <div className="absolute text-sm text-red-500 bg-custom-white -bottom-2 ml-2 px-2">
          {error.message}
        </div>
      )}
    </div>
  );
};
