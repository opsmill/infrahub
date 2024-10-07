import { classNames } from "@/utils/common";
import Prism from "prismjs";
import { ElementRef, forwardRef } from "react";
import Editor from "react-simple-code-editor";

type JsonEditorProps = {
  onChange: (value: string) => void;
  defaultValue?: string;
  disabled?: boolean;
  value?: string;
  className?: string;
  id?: string;
};

export const JsonEditor = forwardRef<ElementRef<typeof Editor>, JsonEditorProps>(
  ({ id, onChange, value, className, ...props }, ref) => {
    return (
      <Editor
        onValueChange={onChange}
        ref={ref}
        textareaId={id}
        ignoreTabKey={true}
        value={value ? (typeof value === "string" ? value : JSON.stringify(value)) : ""}
        style={{
          fontFamily: "'Fira code', 'Fira Mono', monospace",
          fontSize: 12,
        }}
        preClassName="!break-all"
        textareaClassName="!break-all !text-red-100 disabled:cursor-not-allowed disabled:!bg-gray-100 mix-blend-multiply" // text-red-100 needed to make highligted text (in browser search) visible
        className={classNames(
          "w-full rounded-md shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 border-gray-300 text-sm focus-within:ring-2 focus-within:ring-inset focus-within:ring-custom-blue-600 focus-within:border-custom-blue-600 focus-within:outline-none bg-custom-white",
          className
        )}
        {...props}
        padding={10}
        highlight={(code) => Prism.highlight(code, Prism.languages.json, "json")}
      />
    );
  }
);
