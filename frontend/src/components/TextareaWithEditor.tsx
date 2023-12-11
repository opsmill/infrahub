import React, { FC } from "react";
import { MarkdownEditor } from "./MarkdownEditor";
import { classNames } from "../utils/common";

type TextareaWithEditorProps = {
  className?: string;
  defaultValue?: string;
  disabled?: boolean;
  error?: { message?: string };
  onChange: (value: string) => void;
  placeholder?: string;
};

export const TextareaWithEditor: FC<TextareaWithEditorProps> = ({
  className = "",
  defaultValue,
  disabled,
  error,
  onChange,
  placeholder,
}) => {
  const hasError = !!error?.message;

  return (
    <div className="relative">
      <MarkdownEditor
        className={classNames(
          className,
          error?.message
            ? "border-red-500 outline-red-500 focus-within:border-red-500 focus-within:outline-red-600"
            : ""
        )}
        disabled={disabled}
        onChange={onChange}
        defaultValue={defaultValue}
        placeholder={placeholder}
      />

      {hasError && (
        <div className="absolute text-sm text-red-500 bg-custom-white -bottom-2 ml-2 px-2">
          {error.message}
        </div>
      )}
    </div>
  );
};
